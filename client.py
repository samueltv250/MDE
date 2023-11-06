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

        elif command.startswith("start_tracking"):
            self.start_tracking(command)

        elif command.startswith("calibrate_date_time"):
            self.calibrate_date_time(command)

        elif command.startswith("calibrate"):
            self.calibrate(command)

        elif command.startswith("move"):
            self.move(command)

        elif command.startswith("setViewingWindow"):
            self.set_viewing_window(command)

        elif command.startswith("stop_tracking"):
            self.stop_tracking(command)

        elif command.startswith("getMeta"):
            self.get_meta(command)

        elif command.startswith("get"):
            self.get_file(command)

        else:
            raise CommandError(f"'{command}' is not a recognized command.")

    def add_to_queue(self, command):
        # Test
        command = command + " " + """
CSS (TIANHE)            
1 48274U 21035A   23250.60323094  .00028729  00000+0  32278-3 0  9997
2 48274  41.4752  14.6926 0010484 320.3089  39.6983 15.61907922134716
ISS (NAUKA)             
1 49044U 21066A   23250.54606199  .00010692  00000+0  19312-3 0  9994
2 49044  51.6415 280.5283 0005852  40.5829 119.1724 15.50278646414560
FREGAT DEB              
1 49271U 11037PF  23249.81523963  .00005232  00000+0  17878-1 0  9995
2 49271  51.6235  75.4294 0907707 244.0940 106.3644 12.05002786100748
CSS (WENTIAN)           
1 53239U 22085A   23250.41140741  .00030442  00000+0  34184-3 0  9998
2 53239  41.4752  15.8612 0010490 318.7503  41.2543 15.61898836 64117
CSS (MENGTIAN)          
1 54216U 22143A   23250.41140741  .00030442  00000+0  34184-3 0  9999
2 54216  41.4752  15.8612 0010490 318.7503  41.2543 15.61898836134683
TIANZHOU-5              
1 54237U 22152A   23250.41140741  .00030442  00000+0  34184-3 0  9992
2 54237  41.4752  15.8612 0010490 318.7503  41.2543 15.61898836134686
SPORT                   
1 55129U 98067UW  23250.41096130  .00205883  00000+0  74258-3 0  9992
2 55129  51.6227 253.5459 0008158  53.6155 306.5601 15.87498635 39512

CSS (TIANHE): 100, 2000
ISS (NAUKA): 100, 2000"""

        self.send_message(command)
        response = self.receive_full_message()
        print(response)

    def start_tracking(self, command):
        self.send_message(command)
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

    def calibrate(self, command):
        self.send_message(command)
        response = self.receive_full_message()
        print(response)

    def move(self, command):
        self.send_message(command)
        response = self.receive_full_message()
        print(response)

    def set_viewing_window(self, command):
        self.send_message(command)
        response = self.receive_full_message()
        print(response)

    def stop_tracking(self, command):
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
