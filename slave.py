import os
import sys
import bluetooth
import subprocess
from bluetooth import BluetoothSocket, BluetoothError, RFCOMM

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
                subprocess.run(["sudo", "shutdown", "-h", "now"])
                client_sock.send("Shutting down...".encode('utf-8'))
                break
            if data.startswith("reboot"):
                subprocess.run(["sudo", "reboot"])
                client_sock.send("Rebooting...".encode('utf-8'))
                break

            if data.startswith("get"):
                _, file_path = data.split(" ", 1)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    client_sock.send(str(file_size).encode('utf-8'))
                    with open(file_path, "rb") as f:
                        file_data = f.read(1024)
                        while file_data:
                            client_sock.send(file_data)
                            file_data = f.read(1024)
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
