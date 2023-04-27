import serial
import time
from skyfield.api import Topos, Loader

# Load satellite TLE data
load = Loader('~/skyfield_data')
stations_url = 'http://celestrak.com/NORAD/elements/stations.txt'
satellites = load.tle_file(stations_url)
by_name = {sat.name: sat for sat in satellites}
satellite = by_name['ISS (ZARYA)']  # Replace this with the name of the satellite you want to track

# calculate the maximum speed in degrees per second


max_elevation_speed = 180 / 67  # degrees per second
max_azimuth_speed = 360 / 58  # degrees per second



# Set observer location (latitude, longitude, elevation)
observer_location = Topos('40.7128 N', '74.0060 W', elevation_m=10)

serial_port = '/dev/ttyUSB0'
baud_rate = 9600
ser = serial.Serial(serial_port, baud_rate, timeout=1)

def send_command(command):
    ser.write((command + '\r\n').encode())
    time.sleep(0.1)
    response = ser.readline().decode().strip()
    return response

def track_satellite(satellite, observer_location, max_elevation_speed, max_azimuth_speed):
    prev_elevation = None
    prev_azimuth = None
    while True:
        # Calculate current time
        current_time = load.timescale().now()

        # Calculate satellite position
        difference = satellite - observer_location
        topocentric = difference.at(current_time)
        alt, az, _ = topocentric.altaz()

        # Convert radians to degrees
        new_elevation = alt.degrees
        new_azimuth = az.degrees

        if prev_elevation is not None and prev_azimuth is not None:
            # Calculate the difference in position since the last update
            elevation_diff = abs(new_elevation - prev_elevation)
            azimuth_diff = abs(new_azimuth - prev_azimuth)

            # Calculate the time needed to move the rotator
            elevation_time = elevation_diff / max_elevation_speed
            azimuth_time = azimuth_diff / max_azimuth_speed

            # Use the maximum of the two times to avoid overshooting
            sleep_time = max(elevation_time, azimuth_time)

            # Sleep for the calculated time
            time.sleep(sleep_time)

        # Send new position to the rotator
        command = f'W{new_azimuth:03.0f} {new_elevation:03.0f}'
        response = send_command(command)

        # Update previous position
        prev_elevation = new_elevation
        prev_azimuth = new_azimuth


track_satellite(satellite, observer_location, max_elevation_speed, max_azimuth_speed)


