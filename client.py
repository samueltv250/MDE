import os
from bluetooth import BluetoothSocket, RFCOMM, BluetoothError
import time
import pickle
import datetime


class CommandError(Exception):
    def __init__(self, message="Invalid command."):
        super().__init__(message)


class BluetoothManager:
    DATA_BASE_DIR = "/home/pi/Desktop/data_base"

    def __init__(self, device_addr):
        self.device_addr = device_addr
        self.sock = self.connect_to_device()

    def send_message(self, message, is_binary=False):
        data = message if is_binary else message.encode('utf-8')
        msg_len = len(data)
        self.sock.send(str(msg_len).encode('utf-8'))
        time.sleep(0.1)
        while data:
            sent = self.sock.send(data)
            data = data[sent:]

    def receive_full_message(self, as_bytes=False):
        msg_len = int(self.sock.recv(10).decode('utf-8'))
        received_data = []
        bytes_left = msg_len
        while bytes_left > 0:
            chunk = self.sock.recv(min(bytes_left, 1024))
            received_data.append(chunk)
            bytes_left -= len(chunk)
        return b''.join(received_data) if as_bytes else b''.join(received_data).decode('utf-8')

    def connect_to_device(self):
        sock = BluetoothSocket(RFCOMM)
        for port in range(1, 31):
            try:
                print(f"Attempting to connect on RFCOMM channel {port}")
                sock.connect((self.device_addr, port))
                return sock
            except OSError:
                pass
        print("Failed to connect to any port.")
        sock.close()
        return None

    def receive_file(self, file_path, file_size):
        with open(file_path, "wb") as f:
            received = 0
            while received < file_size:
                data = self.sock.recv(1024)
                received += len(data)
                f.write(data)
        print("File received.")

    def run_via_terminal(self):
        try:
            while True:
                command = input("Enter command or 'get <file>': ")
                if command == "exit":
                    self.send_message(command)
                    break
                elif command.startswith("shutdown") or command.startswith("reboot"):
                    self.send_message(command)
                    break
                else:
                    self.interpret_command(command)
        except CommandError as e:
            print(e)
        except KeyboardInterrupt:
            print("\nExiting...")
        except Exception as e:
            print(f"An error occurred: {e}")

    def interpret_command(self, command):
        response = None
        if command.startswith("add_to_queue"):
            self.add_to_queue(command)
        elif command.startswith("calibrate_date_time"):
            self.calibrate_date_time(command)
        elif command.startswith("getMeta"):
            self.get_meta(command)
        elif command.startswith("get"):
            self.get_file(command)
        elif command in ["clear_schedule", "start_tracking", "calibrate", "stop_tracking"]:
            self.send_and_print(command)
        elif command.startswith("move"):
            self.send_and_print(command)
        elif command.startswith("setViewingWindow"):
            self.send_and_print(command)
        else:
            raise CommandError(f"'{command}' is not a recognized command.")

    def add_to_queue(self, command):
        # Open the file and read the contents
        with open('satellites.tle', 'r') as file:
            satellite_data = file.read()
        # Append the file contents to the command
        full_command = command + " \n" + satellite_data
        # Send the full command with the satellite data
        self.send_message(full_command)
        response = self.receive_full_message()
        print(response)


    def calibrate_date_time(self, command):
        self.send_message(command)
        response = self.receive_full_message()
        print(response)

        # Serialize and send the current date time
        current_datetime = datetime.datetime.now()
        time_zone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()
        datetime_info = {
            "datetime": current_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": time_zone
        }
        serialized_data = pickle.dumps(datetime_info)
        self.send_message(serialized_data, is_binary=True)
        response = self.receive_full_message()
        print(response)

    def send_and_print(self, command):
        self.send_message(command)
        response = self.receive_full_message()
        print(response)

    def get_meta(self, command):
        self.send_message(command)
        response = pickle.loads(self.receive_full_message(as_bytes=True))

        # Extract and print the metadata
        current_time = response["current_time"]
        directory_files = response["data"]
        modified_schedule = response["schedule"]
        modified_processed_satellites = response["processed_schedule"]
        tracking_status = response["tracking"]
        time_zone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()

        print(f"Current Time on Raspberry Pi: {current_time.strftime('%Y-%m-%d %H:%M:%S')} {time_zone}")
        print(f"Tracking Status: {'On' if tracking_status else 'Off'}\n")
        print("Directory Files:")
        for file in directory_files.split("\n"):
            print(f"- {file}")
        print("\nSchedule:")
        for satellite in modified_schedule:
            print(f"- Satellite Name: {satellite[0]}")
            print(f"  Rise Time: {satellite[1]}")
            print(f"  Set Time: {satellite[2]}\n")
        print("Processed Schedule:")
        for satellite in modified_processed_satellites:
            print(f"- Satellite Name: {satellite[0]}")
            print(f"  Rise Time: {satellite[1]}")
            print(f"  Set Time: {satellite[2]}\n")

    def get_file(self, command):
        file_path = command.split(" ", 1)[1]
        file_path = os.path.join(self.DATA_BASE_DIR, file_path)
        self.send_message(f"get {file_path}")
        response = self.receive_full_message()
        if response == "File not found":
            print(response)
        else:
            file_size = int(response)
            destination_path = os.path.join(os.getcwd(), os.path.basename(file_path))
            self.receive_file(destination_path, file_size)



def main():
    selected_device = "E4:5F:01:FD:E5:FF"
    print(f"Connecting to {selected_device}")
    manager = BluetoothManager(selected_device)
    manager.run_via_terminal()
    print("Closing socket")
    manager.sock.close()


if __name__ == "__main__":
    main()
