import os
import bluetooth
import subprocess
import threading
import time
from bluetooth import BluetoothSocket, RFCOMM
import scheduler
from datetime import datetime, timedelta
from scheduler import Topos, pytz, determine_timezone
import pickle
import queue
from rtlsdr import RtlSdr
import serial

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

def parse_satellite_data(s):
    lines = s.strip().split('\n')
    satellite_dict = {}

    for line in lines:
        # Split the line at the colon to separate satellite name and frequencies
        name, frequencies = line.split(':')

        # Remove spaces after commas and then split
        freq_list = list(map(int, frequencies.replace(", ", ",").strip().split(',')))

        # Assign the frequency list to the satellite name in the dictionary
        satellite_dict[name.strip()] = freq_list

    return satellite_dict



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



def list_files(directory):
    with os.scandir(directory) as entries:
        return [entry.name for entry in entries if entry.is_file()]







class SatelliteTracker:
    def __init__(self, serial_port='/dev/ttyUSB0', baudrate=9600):

        self.schedule = queue.Queue()

        self.satellites = []
        self.satellites_frequencies = {}
        self.already_processed_satellites = []
        # Flag to stop the tracking process
        self.stop_signal = True
        self.default_frequency = 1e6
        # Placeholder for gps module
        self.latitude = 37.2299995422363
        self.longitude = -80.4179992675781
        self.topos = Topos(latitude_degrees=self.latitude, longitude_degrees=self.longitude, elevation_m=0)
        self.local_timezone = pytz.timezone(determine_timezone(self.latitude, self.longitude))

        # Getting the current UTC time
        utc_now = pytz.utc.localize(datetime.utcnow())
        uts_plus_one_day = utc_now + timedelta(days=1)
        self.start_time = utc_now.astimezone(self.local_timezone)                # Current time

        print("Current time: ", self.start_time)
        print("Timezone: ", self.local_timezone)
        self.end_time = uts_plus_one_day.astimezone(self.local_timezone)        # Current time plus 1 day
        self.ser = serial.Serial(serial_port, baudrate)
        time.sleep(2)  # Allow some time for connection to establish


    def start_tracking(self):
        """Starts the tracking process in a new thread."""
        self.stop_signal = False
        self.tracking_thread = threading.Thread(target=self.run)  # Assign the thread to an instance variable
        self.tracking_thread.start()

    def stop_tracking(self):
        """Stops the tracking process."""
        self.stop_signal = True
        if hasattr(self, 'thread'):
            self.tracking_thread.join()  # Wait for the thread to complete its execution

    def run(self):
        """Method that runs on a separate thread."""
        # once all meta data is set and the schedule is generated,  start tracking
        
        print("Tracking started")
        while not self.stop_signal and self.schedule.qsize() > 0:
            try:
                # Get next item, but don't wait forever. Timeout after 5 seconds, for example.
                item = self.schedule.get(timeout=5)
            except queue.Empty:
                # Queue is empty and no item was retrieved in the given timeout.
                continue

            _, rise_time, set_time, satellite = item
            print(f"Tracking {satellite.name} from {rise_time} to {set_time}")
            self.track_and_record_satellite(satellite, rise_time, set_time)

            # Add the satellite to the list of already processed satellites
            self.already_processed_satellites.append(item)

        self.stop_signal = True


    def concurrent_schedule(self):
        self.schedule_thread = threading.Thread(target=self.create_schedule)  # Assign the thread to an instance variable
        self.schedule_thread.start()

    def create_schedule(self):
        print(f"Creating schedule")

        # self.schedule = scheduler.get_sequential_tracking_schedule(self.satellites, self.start_time, self.end_time, self.latitude, self.longitude, self.topos)
        new_schedule = scheduler.add_to_sequential_schedule(self.schedule, self.satellites, self.start_time, self.end_time, self.latitude, self.longitude, self.topos)

        for item in new_schedule:
            self.schedule.put(item)
        self.satellites = []
        
        print(f"Schedule created")

    def getData(self):
        # returns metadata for GUI, such as directory content, currently tracking satellit, progress
        return
    
    def move_to_position(self, azimuth, elevation):
        """Sends a command to move to a specific azimuth and elevation."""
        cmd = f"MOVE {azimuth} {elevation}\n"
        self.ser.write(cmd.encode('utf-8'))

        # Wait for the response
        while True:
            response = self.ser.readline().decode('utf-8').strip()
            if response == "Moved successfully to position":
                return True
            elif "Error" in response:  # Adjust this condition based on the possible error messages from the Feather
                print("Error:", response)
                return False
            
    def calibrate(self):
        """Sends a command to move to a specific azimuth and elevation."""
        cmd = f"calibrate\n"
        self.ser.write(cmd.encode('utf-8'))

        # Wait for the response
        while True:
            response = self.ser.readline().decode('utf-8').strip()
            if response == "Calibration complete!":
                return True
            elif "Error" in response:  # Adjust this condition based on the possible error messages from the Feather
                print("Error:", response)
                return False
            
    def record(self, satellite, rise_time, set_time):
        # Calculate recording time per frequency based on rise and set time
        total_time = (set_time - rise_time).seconds
        num_frequencies = len(self.satellites_frequencies[satellite.name])
        time_per_frequency = total_time / num_frequencies
        frequencies = self.satellites_frequencies[satellite.name]
        if len(frequencies) == 0:
            print(f"No frequencies for satellite {satellite.name}")
            print(f"Defaulting to 1MHz")
            frequencies = [self.default_frequency]
        # Iterate over the frequencies for the current satellite
        for freq in frequencies:
            # Initialize RTL-SDR device
            sdr = RtlSdr()
            sdr.sample_rate = 2.0486e6
            sdr.center_freq = freq  # Set center frequency
            sdr.gain = 0  # Set gain (could be modified)

            # Calculate number of samples based on time_per_frequency
            number_of_samples = int(sdr.sample_rate * time_per_frequency)

            # Record samples
            samples = sdr.read_samples(number_of_samples)

            # Close RTL-SDR device
            sdr.close()

            # Save samples to a file
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"{satellite.name}_{freq}Hz_{timestamp}.pkl"
            file_path = os.path.join(DATA_BASE_DIR, filename)
            with open(file_path, 'wb') as f:
                pickle.dump(samples, f)

            print(f"Recorded for satellite {satellite.name} at frequency {freq}Hz")

    def track_and_record_satellite(self, satellite, rise_time, set_time):
        # start recording on a separate thread
        self.recording_thread = threading.Thread(target=self.record, args=(satellite, rise_time, set_time))  # Assign the thread to an instance variable
        observer_location = scheduler.wgs84.latlon(self.latitude, self.longitude)
        while self.stop_signal == False:
            
            azimuth, elevation = scheduler.get_azimuth_elevation(satellite, observer_location)
            self.move_to_position(azimuth, elevation)
            continue
    


    def rec_on_exit(self):
        server_sock = BluetoothSocket(RFCOMM)
        server_sock.bind(("", bluetooth.PORT_ANY))
        server_sock.listen(1)

        # before connection is established
        print("Waiting for connection on RFCOMM channel %d" % server_sock.getsockname()[1])

        client_sock, client_info = server_sock.accept()
        print("Accepted connection from", client_info)

        try:
            while True:
                data = receive_full_message(client_sock)
                if not data:
                    break

                print("Received command: %s" % data)

                if data.startswith("shutdown"):
                    subprocess.run(["sudo", "shutdown", "-h", "now"])
                    send_message(client_sock, "Shutting down...")
                    break

                elif data.startswith("reboot"):
                    subprocess.run(["sudo", "reboot"])
                    send_message(client_sock, "Rebooting...")
                    break

                elif data.startswith("calibrate"):
                    self.calibrate()
                    send_message(client_sock, "finished calibrating")
                    break

                elif data.startswith("add_to_queue "):
                    lines = data.split('\n\n')

                    self.satellites = scheduler.load_tle_from_string(lines[0].replace("add_to_queue ", ""))
                    self.satellites_frequencies = parse_satellite_data(lines[1])
                    self.concurrent_schedule()
                    send_message(client_sock, "Updating schedule")

                elif data.startswith("getMeta"):
                    directory_files = '\n'.join(list_files(DATA_BASE_DIR))

                    # Exclude the last column from each row in self.schedule and self.already_processed_satellites
                    modified_schedule = [row[:-1] for row in self.schedule]
                    modified_processed_satellites = [row[:-1] for row in self.already_processed_satellites]

                    meta_data = {"current_time": pytz.utc.localize(datetime.utcnow()), "data": directory_files, "schedule": modified_schedule, "processed_schedule": modified_processed_satellites, "tracking": not self.stop_signal}

                    serialized_data = pickle.dumps(meta_data)
                    send_message(client_sock, serialized_data, is_binary=True)

                elif data.startswith("get"):
                    _, file_path = data.split(" ", 1)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        send_message(client_sock, str(file_size))
                        with open(file_path, "rb") as f:
                            file_data = f.read(1024)
                            while file_data:
                                client_sock.send(file_data)
                                file_data = f.read(1024)
                    else:
                        client_sock.send("File not found".encode('utf-8'))
                    
                elif data.startswith("start_tracking"):
                    self.start_tracking()
                    send_message(client_sock, "Tracking started.")

                elif data.startswith("stop_tracking"):
                    self.stop_tracking()
                    send_message(client_sock, "Tracking stopped.")
       
                else:
                    print("Queue is empty!")

        except Exception as e:
            print("An error occurred:", e)
        finally:
            print("Closing sockets")
            client_sock.close()
            server_sock.close()
            self.rec_on_exit()
                

if __name__ == "__main__":
    # Create SatelliteTracker instance
    tracker = SatelliteTracker()

    # Start listening for commands
    tracker.rec_on_exit()