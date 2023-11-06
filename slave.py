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
import gps

DATA_BASE_DIR = "/home/pi/Desktop/data_base"

def find_arduino_port():
    try:
        # List all devices in /dev/ directory
        devices = os.popen('ls /dev/').read()
        
        # Check for typical Arduino serial port names and return the first match
        for device in ["ttyUSB", "ttyACM"]:
            if device in devices:
                arduino_port = os.popen(f'ls /dev/ | grep {device}').read().split("\n")[0]
                return f"/dev/{arduino_port}"
        return None
    except Exception as e:
        print(f"Error finding Arduino port: {e}")
        return None

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
    def __init__(self, serial_port=None, baudrate=9600):
        # self.gps = gps.init_gps()   # Initialize the GPS module


        if serial_port is None:
            time.sleep(5) # Allow some time for the Raspberry Pi to detect the Arduino
            serial_port = find_arduino_port()
            if serial_port is None:
                print("Unable to find Arduino port.")
        
        self.schedule = queue.Queue()

        self.satellites = []
        self.satellites_frequencies = {}
        self.already_processed_satellites = []
        # Flag to stop the tracking process
        self.stop_signal = True
        self.default_frequency = 1e6
        # Placeholder for gps module
        # self.latitude, self.longitude = gps.get_coordinates(self.gps)
        self.latitude, self.longitude = 37.229572, -80.413940

        self.topos = Topos(latitude_degrees=self.latitude, longitude_degrees=self.longitude, elevation_m=0)
        self.local_timezone = pytz.timezone(determine_timezone(self.latitude, self.longitude))

        self.start_time = None
        self.end_time = None

        print("Current time: ", self.start_time)
        print("Timezone: ", self.local_timezone)

        self.ser = serial.Serial(serial_port, baudrate)
        time.sleep(2)  # Allow some time for connection to establish


    def start_tracking(self):
        """Starts the tracking process in a new thread."""
        self.stop_signal = False
        self.tracking_thread = threading.Thread(target=self.track_and_record_satellites_concurrently)  # Assign the thread to an instance variable
        self.tracking_thread.start()

    def stop_tracking(self):
        """Stops the tracking process."""
        if hasattr(self, 'thread'):
            self.tracking_thread.join()  # Wait for the thread to complete its execution
        
        self.stop_signal = True

    def track_and_record_satellites_concurrently(self):
        print("Tracking started")
        while not self.stop_signal and self.schedule.qsize() > 0:
            try:
                # Get next item, but don't wait forever. Timeout after 5 seconds, for example.
                item = self.schedule.get(timeout=5)
            except queue.Empty:
                # Queue is empty and no item was retrieved in the given timeout.
                continue

            _, rise_time, set_time, satellite = item

            # Wait until rise time or until stop_signal is set
            while self.local_timezone.localize(datetime.now()) < rise_time:
                if self.stop_signal:
                    print(f"Tracking of {satellite.name} canceled.")
                    return  # Exit the method if stop signal is detected
                time.sleep(0.5)  # Sleep for short intervals to check for stop_signal frequently

            print(f"Tracking {satellite.name} from {rise_time} to {set_time}")
            self.track_and_record_satellite(satellite, rise_time, set_time)

            # Add the satellite to the list of already processed satellites
            self.already_processed_satellites.append(item)

        self.stop_signal = True

    def create_schedule(self):
        print(f"Creating schedule")
             # Getting the current UTC time

        utc_now = pytz.utc.localize(datetime.utcnow())
        uts_plus_five_hours = utc_now + timedelta(hours=5) # 5 hours ahead of UTC
        self.start_time = utc_now.astimezone(self.local_timezone)                # Current time
        self.end_time = uts_plus_five_hours.astimezone(self.local_timezone)        # Current time plus 1 day

        old_schedule = []
        while not self.schedule.empty():
            old_schedule.append(self.schedule.get())
        # self.schedule = scheduler.get_sequential_tracking_schedule(self.satellites, self.start_time, self.end_time, self.latitude, self.longitude, self.topos)
        new_schedule = scheduler.add_to_sequential_schedule(old_schedule, self.satellites, self.start_time, self.end_time, self.topos)

        for item in new_schedule:
            self.schedule.put(item)
        self.satellites = []
        
        print(f"Schedule created")
        return new_schedule

    
    def move_to_position(self, azimuth, elevation):
        """Sends a command to move to a specific azimuth and elevation."""
        cmd = f"MOVE {azimuth}, {elevation}\n"
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
            return response
            
    def record(self, satellite, rise_time, set_time):
        # Calculate recording time per frequency based on rise and set time
        total_time = (set_time - rise_time).seconds

        time_per_frequency = total_time
        frequencies = self.satellites_frequencies[satellite.name]
        if len(frequencies) == 0:
            print(f"No frequencies for satellite {satellite.name}")
            print(f"Defaulting to 1MHz")
            freq = self.default_frequency
        else:
            freq = frequencies[0]
            frequencies.pop(0)

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
        # Start recording on a separate thread
        self.recording_thread = threading.Thread(target=self.record, args=(satellite, rise_time, set_time))
        self.recording_thread.start()

        observer_location = scheduler.wgs84.latlon(self.latitude, self.longitude)
        
   
        previous_azimuth, previous_elevation = None, None

        while self.local_timezone.localize(datetime.now()) < set_time:
            azimuth, elevation = scheduler.get_azimuth_elevation(satellite, observer_location)
            
            # Check if this is the first iteration or if the difference in angle is greater than 1 degree
            if previous_azimuth is None or abs(azimuth - previous_azimuth) > 1 or abs(elevation - previous_elevation) > 1:
                self.move_to_position(azimuth, elevation)
                # Update the previous azimuth and elevation
                previous_azimuth, previous_elevation = azimuth, elevation
            
            time.sleep(0.1)
    


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
                elif data.lower().startswith("move"):
                    parts = data.split(" ")
                    command = parts[0]
                    azimuth = float(parts[1])
                    elevation = float(parts[2])
                    msg = self.move_to_position(azimuth, elevation)
                    send_message(client_sock, msg)
                    
                elif data.startswith("calibrate_date_time"):
                    send_message(client_sock, "Waiting on date time info")
                    datetime_info = pickle.loads(receive_full_message(client_sock, as_bytes=True))
                    received_datetime = datetime.strptime(datetime_info['datetime'], "%Y-%m-%d %H:%M:%S")

                    # Format the datetime for the 'date -s' command
                    formatted_datetime = received_datetime.strftime("%Y-%m-%d %H:%M:%S")
                    # Set the system date and time
                    subprocess.call(['sudo', 'date', '-s', formatted_datetime])

                    # Set the time zone
                    time_zone = datetime_info['timezone']
                    subprocess.call(['sudo', 'timedatectl', 'set-timezone', time_zone])
                    send_message(client_sock, "Finished setting datetime")
                elif data.startswith("calibrate"):
                    msg = self.calibrate()
                    send_message(client_sock, msg)

                # setViewingWindow
                elif data.startswith("setViewingWindow"):
                    parts = data.split(" ")
                    command = parts[0]
                    start_time = " ".join(parts[1:3])  # Joins the second and third parts
                    end_time = " ".join(parts[3:5])  # Joins the fourth and fifth parts

                    # time are entered in the local timezone, must make timezone aware
                    start_time = self.local_timezone.localize(datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S"))
                    end_time = self.local_timezone.localize(datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S"))
                    self.start_time = start_time
                    self.end_time = end_time

                elif data.startswith("add_to_queue "):
                    lines = data.split('\n\n')

                    self.satellites = scheduler.load_tle_from_string(lines[0].replace("add_to_queue ", ""))
                    self.satellites_frequencies = parse_satellite_data(lines[1])
                    # start generating schedule once all meta data is set, the default time range is 5 hours
                    if self.start_time is None:
                        utc_now = pytz.utc.localize(datetime.utcnow())
                        uts_plus_five_hours = utc_now + timedelta(hours=5)
                        self.start_time = utc_now.astimezone(self.local_timezone)
                        self.end_time = uts_plus_five_hours.astimezone(self.local_timezone)
                    new_schedule = self.create_schedule()
                    send_message(client_sock, "Schedule updated")

                elif data.startswith("clear_schedule"):
                    with self.schedule.mutex:  # Acquire the lock before clearing
                        self.schedule.queue.clear()  # Clear all items from the queue
                    send_message(client_sock, "Schedule cleared")



                elif data.startswith("getMeta"):
                    directory_files = '\n'.join(list_files(DATA_BASE_DIR))

                    # Exclude the last column from each row in self.schedule and self.already_processed_satellites
                    modified_schedule = [row[:-1] for row in list(self.schedule.queue)]
                    modified_processed_satellites = [row[:-1] for row in self.already_processed_satellites]

                    meta_data = {"current_time": pytz.utc.localize(datetime.utcnow()), "data": directory_files, "schedule": modified_schedule, "processed_schedule": modified_processed_satellites, "tracking": not self.stop_signal}

                    serialized_data = pickle.dumps(meta_data)
                    send_message(client_sock, serialized_data, is_binary=True)

                elif data.startswith("get"):
                    _, file_path, chuck_size = data.split(" ")
                    chuck_size = int(chuck_size)
                    print("size "+str(chuck_size))
                    
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        send_message(client_sock, str(file_size))
                        with open(file_path, "rb") as f:
                            file_data = f.read(chuck_size)
                            while file_data:
                                client_sock.send(file_data)
                                file_data = f.read(chuck_size)
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
    tracker = SatelliteTracker()
    tracker.rec_on_exit()