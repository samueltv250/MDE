import os
from bluetooth import BluetoothSocket, BluetoothError, RFCOMM
import time
import pickle


class CommandError(Exception):
    def __init__(self, message="Invalid command."):
        self.message = message
        super().__init__(self.message)


DATA_BASE_DIR = "/home/pi/Desktop/data_base"
def send_message(sock, message, is_binary=False):
    # Serialize the message as bytes if it's not already
    data = message if is_binary else message.encode('utf-8')

    # Send message length first
    msg_len = len(data)
    sock.send(str(msg_len).encode('utf-8'))
    time.sleep(0.1)  # Small delay to allow the receiver to prepare
    
    # Send the actual message
    while data:
        sent = sock.send(data)
        data = data[sent:]


def receive_full_message(sock, as_bytes=False):
    # First, get the message length
    msg_len = int(sock.recv(10).decode('utf-8'))
    received_data = []
    bytes_left = msg_len
    while bytes_left > 0:
        chunk = sock.recv(min(bytes_left, 1024))
        received_data.append(chunk)
        bytes_left -= len(chunk)

    if as_bytes:
        return b''.join(received_data)
    else:
        return b''.join(received_data).decode('utf-8')


def connect_to_device(device_addr):
    sock = BluetoothSocket(RFCOMM)
    for port in range(1, 31):  # Try ports 1 through 30
        try:
            print("Attempting to connect on RFCOMM channel %d" % port)

            sock.connect((device_addr, port))
            return sock
        except OSError as e:
            pass
    print("Failed to connect to any port.")
    sock.close()
    return None

def receive_file(sock, file_path, file_size):
    with open(file_path, "wb") as f:
        received = 0
        while received < file_size:
            data = sock.recv(1024)
            received += len(data)
            f.write(data)
    print("File received.")

def run_via_terminal(sock):
 
    while True:
        try:
            command = input("Enter command or 'get <file>': ")
            if command == "exit":
                send_message(sock, command)
                break
            elif command.startswith("shutdown") or command.startswith("reboot"):
                send_message(sock, command)
                break
                
            else:
                interpret_command(command, sock)
        except CommandError as e:
            print(e)
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            break


def interpret_command(command, sock):
    response = None
    if command.startswith("add_to_queue"):  # New command to add satellite to the queue
        # Test TLE file to send
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
        send_message(sock, command)
        response = receive_full_message(sock)

    elif command.startswith("start_tracking"):
        send_message(sock, command)
        response = receive_full_message(sock)

    elif command.startswith("calibrate"):
        send_message(sock, command)
        response = receive_full_message(sock)

    elif command.startswith("move"):
        # bandwidth, centerfrequency, samplerate
        send_message(sock, command)
        response = receive_full_message(sock)

    elif command.startswith("getMeta"):
        send_message(sock, command)
        response = pickle.loads(receive_full_message(sock, as_bytes=True))

        # Extracting the components from the response for better readability
        current_time = response["current_time"]
        directory_files = response["data"]
        modified_schedule = response["schedule"]
        modified_processed_satellites = response["processed_schedule"]
        tracking_status = response["tracking"]

        # Print current time
        print(f"Current Time on Raspberry Pi: {current_time}")

        # Print tracking status
        print(f"Tracking Status: {'On' if tracking_status else 'Off'}\n")

        # Print list of files
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
        return response
    elif command.startswith("get"):
        file_path = command.split(" ", 1)[1]
        #  directory where the files are stored locall
        file_path = DATA_BASE_DIR + "/" + file_path
        command = "get " + file_path
        send_message(sock, command)
        response = receive_full_message(sock)
        if response == "File not found":
            print(response)
        else:
            file_size = int(response)
            destination_path = os.path.join(os.getcwd(), os.path.basename(file_path))
            receive_file(sock, destination_path, file_size)
        
    else:
        raise CommandError(f"'{command}' is not a recognized command.")
    print(response)
    return response


def main():
    # unique MAC address for Raspberry Pi (slave)
    selected_device = "E4:5F:01:FD:E5:FF"
    print("Connecting to {}".format(selected_device))
    sock = connect_to_device(selected_device)

    try:
        run_via_terminal(sock)
    except BluetoothError as e:
        print("Disconnected")
    finally:
        print("Closing socket")
        sock.close()

if __name__ == "__main__":
    main()