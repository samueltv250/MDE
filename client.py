import sys
import bluetooth
from bluetooth import BluetoothSocket, BluetoothError, RFCOMM, discover_devices

def search_devices():
    nearby_devices = discover_devices()
    print("Found {} devices.".format(len(nearby_devices)))

    for addr, name in nearby_devices:
        print("  {} - {}".format(addr, name))
    return nearby_devices

def connect_to_device(device_addr):
    sock = BluetoothSocket(RFCOMM)
    sock.connect((device_addr, 1))
    return sock

def main():
    print("Searching for devices...")

    selected_device = "E4:5F:01:FD:E5:FF"
    
    print("Connecting to {}".format(selected_device))
    sock = connect_to_device(selected_device)

    try:
        while True:
            command = input("Enter command or 'get <file_path>': ")
            if command == "exit":
                break
            sock.send(command.encode('utf-8'))
            if command.startswith("shutdown"):
                break
           # ...

     
            if command.startswith("get"):
                with open(command.split(" ", 1)[1], "wb") as f:
                    while True:
                        data = sock.recv(1024)
                        if data.endswith(b'EOF'):
                            f.write(data[:-3])  # Write received data without 'EOF' marker
                            break
                        else:
                            f.write(data)
                print("File received.")





    except BluetoothError as e:
        print("Disconnected")

    finally:
        print("Closing socket")
        sock.close()

if __name__ == "__main__":
    main()
