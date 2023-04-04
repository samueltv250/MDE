import os
import sys
import bluetooth
from bluetooth import BluetoothSocket, BluetoothError, RFCOMM, discover_devices
import time
import os
os.chdir('/home/pi')

def rec_on_exit():
    server_sock = BluetoothSocket(RFCOMM)
    server_sock.bind(("", bluetooth.PORT_ANY))
    server_sock.listen(1)

    print("Waiting for connection on RFCOMM channel %d" % server_sock.getsockname()[1])

    client_sock, client_info = server_sock.accept()
    print("Accepted connection from", client_info)

    try:
        while True:
            data = client_sock.recv(1024).decode('utf-8')
            if not data:
                break
            print("Received command: %s" % data)
            if data.startswith("shutdown"):
                time.sleep(1)
                os.system("shutdown now -h")
            if data.startswith("get"):
                _, file_path = data.split(" ", 1)
                if os.path.isfile(file_path):
                    with open(file_path, "rb") as f:
                        file_data = f.read()
                        file_size = len(file_data)
                        client_sock.send(f"{file_size}\n".encode('utf-8'))
                        time.sleep(0.5)  # Allow some time for the client to be ready
                        client_sock.sendall(file_data)
                else:
                    client_sock.send("File not found".encode('utf-8'))
            else:
                os.system(data)

    except BluetoothError as e:
        print("Disconnected")

    finally:
        print("Closing sockets")
        client_sock.close()
        server_sock.close()
        rec_on_exit()

rec_on_exit()
