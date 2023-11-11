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
import SoapySDR as sdr
import shutil


DATA_BASE_DIR = "/home/dietpi/Desktop/MDE/data_base"
CF32 = sdr.SOAPY_SDR_CF32  # Data format for SoapySDR: complex float 32 bits

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
        self.default_frequency = 1.626e9
        # Placeholder for gps module
        # self.latitude, self.longitude = gps.get_coordinates(self.gps)
        self.latitude, self.longitude = 37.229572, -80.413940

        self.topos = Topos(latitude_degrees=self.latitude, longitude_degrees=self.longitude, elevation_m=0)
        self.local_timezone = pytz.timezone(determine_timezone(self.latitude, self.longitude))

        self.start_time = None
        self.end_time = None

        self.samples_queue = [queue.Queue(), queue.Queue()]
        self.recording = True
        
        print("Current time: ", self.start_time)
        print("Timezone: ", self.local_timezone)

        self.ser = serial.Serial(serial_port, baudrate)
        time.sleep(2)  # Allow some time for connection to establish


        devices = sdr.Device.enumerate()
        for dev in devices:
            if dev["label"].strip() == "SDRplay Dev0 RSPduo 230102CE34 - Single Tuner":
                single_device_args = dev
            elif dev["label"].strip() == "SDRplay Dev1 RSPduo 230102CE34 - Dual Tuner":
                dual_device_args = dev



        # initialize receiver in single and dual mode
        self.singleSdr = sdr.Device(single_device_args)
        self.dualSdr = sdr.Device(dual_device_args)




        self.mainSdr = sdr.Device(dual_device_args)
        self.sample_rate = 2e6


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
                # queue is empty and no item was retrieved in the given timeout.
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
            if response.lower() == "moved":
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
            
   

        sdr_device = self.mainSdr
        # Setup SDR device and stream
        gain = 30  # Gain in dB
        sdr_device.setSampleRate(sdr.SOAPY_SDR_RX, 0, self.sample_rate)
        sdr_device.setFrequency(sdr.SOAPY_SDR_RX, 0, freq1)
        sdr_device.setGain(sdr.SOAPY_SDR_RX, 0, gain)

        stream0 = sdr_device.setupStream(sdr.SOAPY_SDR_RX, sdr.SOAPY_SDR_CF32)
        sdr_device.activateStream(stream0)

        self.recording = True
        # Buffer settings
        buffer_size = 1024
        num_samples = int(self.sample_rate)*total_time

        iq_queue = queue.Queue(maxsize=100)

        # total_bytes, used_bytes, free_bytes = shutil.disk_usage(DATA_BASE_DIR)
        # used = total_bytes / (1024 ** 3)  # Convert from bytes to gigabytes

        # if used > 10:
        #     print(f"Not enough disk space: only {free_gb:.2f} GB available.")
        #     self.recording = False
        #     return  # Exit the function if there isn't enough space
        # Event to signal when to stop
        stop_event = threading.Event()
        # Function to read from the SDR (Producer)
        def read_from_sdr(sdr, rx_stream, buffer_size, num_samples, iq_queue, stop_event):
            buff = np.empty(buffer_size, dtype=np.complex64)
            samples_collected = 0
            
            while not stop_event.is_set()  and samples_collected < num_samples:
                sr = sdr.readStream(rx_stream, [buff], buffer_size)
                if sr.ret > 0:
                    iq_queue.put(buff[:sr.ret])  # Put a copy of the buffer into the queue
                    samples_collected += sr.ret
                elif sr.ret == -1:
                    print("Overflow occurred")

        self.total_sample = 0

        def process_iq_samples(iq_queue, stop_event):
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{satellite.name}_{freq1}Hz_{timestamp}.pkl"
            file_path = os.path.join(DATA_BASE_DIR, filename)

            with open(file_path, 'wb') as file:
                while not (stop_event.is_set() and iq_queue.empty()):
                    try:
                        
                        # Retrieve a block of samples from the queue
                        samples = iq_queue.get(timeout=1)
                        self.total_sample += len(samples)

                        # Pickle the numpy array directly to avoid the memory overhead of extending a list
                        print('dumping')
                        pickle.dump(samples, file)
                    except queue.Empty:
                        continue
        producer_thread = threading.Thread(target=read_from_sdr, args=(sdr_device, stream0, buffer_size, num_samples, iq_queue, stop_event))
        consumer_thread = threading.Thread(target=process_iq_samples, args=(iq_queue, stop_event))

        producer_thread.start()
        consumer_thread.start()



        # Wait for the producer to finish reading
        producer_thread.join()

        # Signal the consumer to stop processing and exit
        stop_event.set()

        # Wait for the consumer to finish processing
        consumer_thread.join()
        print("Extracted "+ str(self.total_sample)+" samples")
        sdr_device.deactivateStream(stream0)
        sdr_device.closeStream(stream0)
        sdr_device = None

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
    


    def rec_on_exit(self, ip_address='0.0.0.0', port=12345):
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

                    elif data.startswith("set_single_tuner"):
                        self.mainSdr = self.singleSdr
                        self.sample_rate = 10e6
                        send_message(client_sock, "set_single_tuner")
                        
                    elif data.startswith("set_dual_tuner"):
                        self.mainSdr = self.dualSdr
                        self.sample_rate = 2e6
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
    tracker = SatelliteTracker()
    tracker.rec_on_exit()
    # rise_time = datetime.now()
    # test_dict = {"name":"test"}
    # tracker.record(test_dict, rise_time, rise_time+timedelta(seconds=1))