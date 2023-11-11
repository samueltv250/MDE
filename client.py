import os
import time
import pickle
import datetime
import socket

class CommandError(Exception):
    def __init__(self, message="Invalid command."):
        super().__init__(message)


class WiFiManager:

    def __init__(self, device_addr):
        self.device_addr = device_addr
        self.sock = self.connect_to_device(device_addr)

    def send_message(self, message, is_binary=False):
        data = message if is_binary else message.encode('utf-8')
        msg_len = len(data)
        self.sock.send(str(msg_len).encode('utf-8'))
        time.sleep(0.5)
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

    def connect_to_device(self, ip_address, port=12345):
        
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)  # Set the timeout for the connection attempt to 10 seconds
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 32 * 1024)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32 * 1024)

            try:
                print(f"Attempting to connect on RFCOMM channel {port}")
                sock.connect((ip_address, port))
                sock.settimeout(None)  # Reset the timeout to None after a successful connection
                return sock
            except socket.timeout:
                print("Connection attempt timed out after 10 seconds, retrying...")
            except Exception as e:
                print(f"Failed to connect due to an error: {e}")
                time.sleep(1)  # Wait a bit before retrying to avoid spamming connection attempts

                


    def receive_file(self, file_path, file_size, chunck_size):
        with open(file_path, "wb") as f:
            received = 0
            while received < file_size:
                data = self.sock.recv(chunck_size)
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
            start_time = time.time()
            self.get_file(command, 104857600)
            end_time = time.time()
            print(f"Time taken to receive file: {end_time - start_time} seconds")
            
        elif command in ["clear_schedule", "start_tracking", "calibrate", "stop_tracking", "device_get", "set_single_tuner", "set_dual_tuner"]:
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
        used_space = response["used_space"]
        current_time = response["current_time"]
        used_dir = response["directory"]
        is_recording = response["is_recording"]
        directory_files = response["data"]
        modified_schedule = response["schedule"]
        modified_processed_satellites = response["processed_schedule"]
        tracking_status = response["tracking"]
        time_zone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()

        print(f"Current Time on Raspberry Pi: {current_time.strftime('%Y-%m-%d %H:%M:%S')} {time_zone}\n")
        print(f"Tracking Status: {'On' if tracking_status else 'Off'}\n")
        print(f"Recording Status: {'On' if is_recording else 'Off'}\n")
        print(f"Using directory: {used_dir}\n")
        print(f"Total GB used in directory: {used_space}")

        

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

    def get_file(self, command, chunck_size = 4096):
        file_path = command.split(" ", 1)[1]
        message = f"get {file_path} {chunck_size}"
        self.send_message(message)
        response = self.receive_full_message()
        if response == "File not found":
            print(response)
        else:
            file_size = int(response)
            destination_path = os.path.join(os.getcwd(), os.path.basename(file_path))
            self.receive_file(destination_path, file_size, chunck_size)



def main():
    server_ip = "192.168.220.1"  # The IP address of the Raspberry Pi when it's a hotspot
    print(f"Connecting to {server_ip}")
    manager = WiFiManager(server_ip)
    manager.run_via_terminal()
    print("Closing socket")
    manager.sock.close()




if __name__ == "__main__":
    main()
