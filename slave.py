import os
import socket
import subprocess
import threading
import time
import scheduler
from datetime import datetime, timedelta
from scheduler import Topos, pytz, determine_timezone
import pickle
import queue
from rtlsdr import RtlSdr
import serial
import gps
import numpy as np
from sdr_recorder import SDRRecorder, sdr





DATA_BASE_DIR = "/home/dietpi/Desktop/MDE/data_base"

USB_DIR = "/mnt/usbdrive"


def get_size_of_directory(directory_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directory_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is a symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size / (1024 * 1024 * 1024)  # Convert to GB


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
    time.sleep(0.5)  # Small delay to allow the receiver to prepare
    
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
        self.arduino_found = True
        time.sleep(5) #give time to initialize
        if serial_port is None:
            time.sleep(5) # Allow some time for the Raspberry Pi to detect the Arduino
            serial_port = find_arduino_port()
            if serial_port is None:
                print("Unable to find Arduino port.")
                self.arduino_found = False
        self.schedule = queue.Queue()
        self.stop_recording_event = threading.Event()
        self.satellites = []
        self.satellites_frequencies = {}
        self.already_processed_satellites = []
        # Flag to stop the tracking process
        self.stop_signal = True
        self.default_frequency = 1.626e9
        # Placeholder for gps module
        # self.latitude, self.longitude = gps.get_coordinates(self.gps)
        self.latitude, self.longitude = 37.229572, -80.413940

        self.topos = Topos(latitude_degrees=self.latitude, longitude_degrees=self.longitude, elevation_m=0)
        self.local_timezone = pytz.timezone(determine_timezone(self.latitude, self.longitude))
        
        self.start_time = None
        self.end_time = None

        self.samples_queue = [queue.Queue(), queue.Queue()]
        self.recording = False
        
        print("Current time: ", self.start_time)
        print("Timezone: ", self.local_timezone)

        self.ser = serial.Serial(serial_port, baudrate)
        time.sleep(2)  # Allow some time for connection to establish

        self.dual_device_args = ""
        self.single_device_args = ""
        devices = sdr.Device.enumerate()
        for dev in devices:
            print(dev)
            if "Single Tuner" in dev["label"]:
                self.single_device_args = dev
            elif "Dual Tuner" in dev["label"]:
                self.dual_device_args = dev
   
        self.sample_rate = 10e6
        self.dualMode = False


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
        self.stop_recording_event.set()
        self.recording = False

    def track_and_record_satellites_concurrently(self):
        try:
            print("Tracking started")
            while not self.stop_signal and self.schedule.qsize() > 0:
    
                if self.schedule.qsize() == 0:
                    break
                item = self.schedule.queue[0] if not self.schedule.empty() else None
                if item == None:
                    self.stop_signal = True
                _, rise_time, set_time, satellite = item
                # now = rise_time+ timedelta(minutes=1)
                while self.local_timezone.localize(datetime.now())  < rise_time:
                    print("waiting")
                    print(self.local_timezone.localize(datetime.now())+ timedelta(hours=2))
                    print(rise_time)
                    if self.stop_signal:
                        print(f"Tracking got canceled before it began.")
                        return  # Exit the method if stop signal is detected
                    time.sleep(0.5)  # Sleep for short intervals to check for stop_signal frequently


                try:
                    # Get next item, but don't wait forever. Timeout after 5 seconds, for example.
                    item = self.schedule.get(timeout=5)
                    


                except queue.Empty:
                    # queue is empty and no item was retrieved in the given timeout.
                    self.stop_signal = True
                    break

                _, rise_time, set_time, satellite = item



                print(f"Tracking {satellite.name} from {rise_time} to {set_time}")
                self.track_and_record_satellite(satellite, rise_time, set_time)

                # Add the satellite to the list of already processed satellites
                self.already_processed_satellites.append(item)
        except Exception as e:
            print("Error occured during tracking: {e}")
        finally:
            self.stop_signal = True


    def create_schedule(self):
        print(f"Creating schedule")
             # Getting the current UTC time
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
        if self.arduino_found:
            cmd = f"MOVE {azimuth}, {elevation}\n"
            self.ser.write(cmd.encode('utf-8'))

            # Wait for the response
            while True:
                response = self.ser.readline().decode('utf-8').strip()
                if response.lower() == "moved":
                    return True
                elif "Error" in response:  # Adjust this condition based on the possible error messages from the Feather
                    print("Error:", response)
                    return False
        else:
            return False
    def calibrate(self):
        """Sends a command to move to a specific azimuth and elevation."""
        if self.arduino_found:
            cmd = f"calibrate\n"
            self.ser.write(cmd.encode('utf-8'))

            # Wait for the response
            while True:
                response = self.ser.readline().decode('utf-8').strip()
                return response
        else:
            return "arduino not found"

    def record(self, satellite, rise_time, set_time):


        total_time = (set_time - rise_time).seconds
        if self.satellites_frequencies.get(satellite.name) is None or len (self.satellites_frequencies.get(satellite.name)) == 0:
            print(f"No frequencies for satellite {satellite.name}, defaulting to {self.default_frequency}")
            freq1 = self.default_frequency
        elif len(self.satellites_frequencies.get(satellite.name)) == 1:
            freq1 = self.satellites_frequencies[satellite.name][0]
            self.satellites_frequencies.pop(satellite.name)
        else:
            freq1 = self.satellites_frequencies[satellite.name][0]
            self.satellites_frequencies[satellite.name] = self.satellites_frequencies[satellite.name][1:]
            
        self.stop_signal = False
        self.recording = True
        gain = 30


        self.stop_recording_event = threading.Event()



        
       

        
        used = get_size_of_directory(DATA_BASE_DIR)
        bits_per_sample = 32
        bytes_per_sample = bits_per_sample/8
        theoretical_recording_size = (self.sample_rate * bytes_per_sample * total_time) / (1024**3)
        projected_used_space = theoretical_recording_size + used
        print("Theoretical space used: "+str(theoretical_recording_size))
        if projected_used_space > 120:
            print(f"recording would exceed max space in drive, must clean drive to continue recording")
            self.recording = False
            self.stop_signal = True
            self.stop_recording_event.set()
            return  # Exit the function if there isn't enough space

        try:
            if self.dualMode:
                recorder = SDRRecorder(self.dual_device_args, sat_name = satellite.name, mode='dual', frequency = self.default_frequency, stop_event = self.stop_recording_event)
            else:
                recorder = SDRRecorder(self.single_device_args, sat_name = satellite.name, mode='single', frequency = self.default_frequency, stop_event = self.stop_recording_event)
            recorder.start_recording(30, total_time)
            recorder.stop_recording()
        except:
            print("Error recording")
            self.recording = False
            self.stop_signal = True


        
        

    def track_and_record_satellite(self, satellite, rise_time, set_time):
        # Start recording on a separate thread
        self.recording_thread = threading.Thread(target=self.record, args=(satellite, rise_time, set_time))
        self.recording_thread.start()
        

        observer_location = scheduler.wgs84.latlon(self.latitude, self.longitude)
        
   
        previous_azimuth, previous_elevation = None, None

        while self.local_timezone.localize(datetime.now()) < set_time and self.stop_signal is False and self.recording is True:
            azimuth, elevation = scheduler.get_azimuth_elevation(satellite, observer_location)
            
            # Check if this is the first iteration or if the difference in angle is greater than 1 degree
            if previous_azimuth is None or abs(azimuth - previous_azimuth) > 1 or abs(elevation - previous_elevation) > 1:
                self.move_to_position(azimuth, elevation)
                # Update the previous azimuth and elevation
                previous_azimuth, previous_elevation = azimuth, elevation
            
            time.sleep(0.1)
            
    


    def rec_on_exit(self, ip_address='0.0.0.0', port=22325):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Set the SO_REUSEADDR option
        
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 32 * 1024)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32 * 1024)

        
        
        server_sock.bind((ip_address, port))
        server_sock.listen(1)
        while True:
            print(f"Waiting for connection on IP {ip_address} port {port}")
            client_sock = None
            try:
                client_sock, client_info = server_sock.accept()
                print("Accepted connection from", client_info)
                while True:
                    data = receive_full_message(client_sock)
                    if not data:
                        break

                    print("Received command: %s" % data)

                    if data.startswith("shutdown"):
                        subprocess.run(["sudo", "shutdown", "-h", "now"])
                        send_message(client_sock, "Shutting down...")
                        server_sock.close()
                        return

                    elif data.startswith("reboot"):
                        subprocess.run(["sudo", "reboot"])
                        send_message(client_sock, "Rebooting...")
                        server_sock.close()
                        return
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
                        # Set the time zone
                        time_zone = datetime_info['timezone']
                        subprocess.call(['sudo', 'timedatectl', 'set-timezone', time_zone])
                        # Format the datetime for the 'date -s' command
                        formatted_datetime = received_datetime.strftime("%Y-%m-%d %H:%M:%S")
                        # Set the system date and time
                        subprocess.call(['sudo', 'date', '-s', formatted_datetime])


                        send_message(client_sock, "Finished setting datetime")
                    elif data.startswith("calibrate"):
                        msg = self.calibrate()
                        send_message(client_sock, msg)

                    elif data.startswith("set_single_tuner"):
                        self.sample_rate = 10e6
                        self.dualMode = False
                        send_message(client_sock, "set_single_tuner")
                        
                    elif data.startswith("set_dual_tuner"):
                        self.sample_rate = 2e6
                        self.dualMode = True
                        send_message(client_sock, "set_dual_tuner")

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
                        send_message(client_sock, "setViewingWindow")
             
                    elif data.startswith("setCord"):
                        parts = data.split(" ")
                        command = parts[0]
                        latitude = parts[1]
                        longitude = parts[2]
                        self.latitude = float(latitude)
                        self.longitude = float(longitude)
                        send_message(client_sock, "setCord")
                                

                    elif data.startswith("add_to_queue "):
                        lines = data.split('\n\n')

                        self.satellites = scheduler.load_tle_from_string(lines[0].replace("add_to_queue ", ""))
                        self.satellites_frequencies = parse_satellite_data(lines[1])
                        # start generating schedule once all meta data is set, the default time range is 8 hours
                        if self.start_time is None:
                            utc_now = pytz.utc.localize(datetime.utcnow())
                            uts_plus_five_hours = utc_now + timedelta(hours=8)
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

                        meta_data = {"used_space" : get_size_of_directory(DATA_BASE_DIR), "is_recording" :self.recording,"directory" :DATA_BASE_DIR, "current_time": pytz.utc.localize(datetime.utcnow()), "data": directory_files, "schedule": modified_schedule, "processed_schedule": modified_processed_satellites, "tracking": not self.stop_signal}

                        serialized_data = pickle.dumps(meta_data)
                        send_message(client_sock, serialized_data, is_binary=True)

                    elif data.startswith("get"):
                        _, file_path, chuck_size = data.split(" ")
                        file_path = DATA_BASE_DIR+"/"+file_path
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
                        self.stop_signal = False
                        self.start_tracking()
                        send_message(client_sock, "Tracking started.")

                    elif data.startswith("device_get"):
                        devices = sdr.Device.enumerate()
                        final_response = ""
                        for i, dev in enumerate(devices):
                            print(f"Device {i}: {dev}")
                            final_response += f"Device {i}: {dev}\n"
                        
                        send_message(client_sock, final_response)

                    elif data.startswith("stop_tracking"):
                        self.stop_tracking()
                        send_message(client_sock, "Tracking stopped.")
        
                    else:
                        print("queue is empty!")

            except socket.error as e:
                print(f"Socket error: {e}")
                time.sleep(1)
            except Exception as e:
                print(f"An unexpected error occurred: {e}")
            finally:
                if client_sock:
                    client_sock.close()




if __name__ == "__main__":
    if os.path.isdir(USB_DIR):
        DATA_BASE_DIR = USB_DIR


    tracker = SatelliteTracker()



    tracker.rec_on_exit()
