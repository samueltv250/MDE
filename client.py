import sys
import bluetooth
import os
from bluetooth import BluetoothSocket, BluetoothError, RFCOMM

def connect_to_device(device_addr):
    sock = BluetoothSocket(RFCOMM)
    try:
        sock.connect((device_addr, 1))
    except OSError as e:
        print("Could not connect. Error:", e)
        sock.close()
        print("Retrying to connect.")
        return connect_to_device(device_addr)
    return sock

def receive_file(sock, file_path, file_size):
    with open(file_path, "wb") as f:
        received = 0
        while received < file_size:
            data = sock.recv(1024)
            received += len(data)
            f.write(data)
    print("File received.")

def main():
    selected_device = "E4:5F:01:FD:E5:FF"
    print("Connecting to {}".format(selected_device))
    sock = connect_to_device(selected_device)

    try:
        while True:
            command = input("Enter command or 'get <file_path>': ")
            if command == "exit":
                break
            sock.send(command.encode('utf-8'))
            if command.startswith("shutdown") or command.startswith("reboot"):
                response = sock.recv(1024).decode('utf-8')
                print(response)
                break
            if command.startswith("get"):
                file_path = command.split(" ", 1)[1]
                response = sock.recv(1024).decode('utf-8')
                if response == "File not found":
                    print(response)
                else:
                    file_size = int(response)
                    destination_path = os.path.join(os.getcwd(), os.path.basename(file_path))
                    receive_file(sock, destination_path, file_size)
    except BluetoothError as e:
        print("Disconnected")
    finally:
        print("Closing socket")
        sock.close()

if __name__ == "__main__":
    main()
