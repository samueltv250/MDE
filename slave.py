import os
import sys
import bluetooth
import subprocess
import threading
import time
from bluetooth import BluetoothSocket, BluetoothError, RFCOMM
import queue

class SatelliteTracker:
    def __init__(self):
        # Placeholder for a list of satellites in the schedule
        self.schedule = []
        self.task_queue = queue.Queue()

    def add_to_schedule(self, satellite_name):
        """Add satellite name to the schedule."""
        self.schedule.append(satellite_name)
        print(f"Added {satellite_name} to the schedule!")

    def run(self):
        """Method to continuously check the queue and process items."""
        while True:
            for i in range(10):
                print(f"Tracking 1")
                time.sleep(1)
            # Wait for an item to be added to the queue

            try:
                satellite_name = self.task_queue.get_nowait()
                self.add_to_schedule(satellite_name)
            except queue.Empty:
                continue

    def rec_on_exit(self):
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
                elif data.startswith("reboot"):
                    subprocess.run(["sudo", "reboot"])
                    client_sock.send("Rebooting...".encode('utf-8'))
                    break
                elif data.startswith("add_to_queue"):
                    self.task_queue.put("satellite_name")
                    client_sock.send(f"Added to queue".encode('utf-8'))
                    continue
                elif data.startswith("get"):
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
                # else:
                #     os.system(data)
        except BluetoothError as e:
            print("Disconnected")
        finally:
            print("Closing sockets")
            client_sock.close()
            server_sock.close()
                

if __name__ == "__main__":
    # Create SatelliteTracker instance
    tracker = SatelliteTracker()
    # Start the main method in a new thread
    threading.Thread(target=tracker.run).start()
    # Start listening for commands
    tracker.rec_on_exit()