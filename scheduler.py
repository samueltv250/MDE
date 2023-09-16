from skyfield.api import Topos, load, EarthSatellite


from datetime import datetime
import pytz
import io
from timezonefinder import TimezoneFinder

ts = load.timescale()


def get_all_viewing_windows(satellite, start_time, end_time, topos, latitude, longitude):

    start_time = start_time.astimezone(pytz.utc)
    end_time = end_time.astimezone(pytz.utc)
    # Convert the start and end time to a Time instance
    t0 = ts.utc(start_time.year, start_time.month, start_time.day, start_time.hour, start_time.minute, start_time.second)
    t1 = ts.utc(end_time.year, end_time.month, end_time.day, end_time.hour, end_time.minute, end_time.second)
    # Find all the windows where the satellite is above 0 degrees elevation
    times, events = satellite.find_events(topos, t0, t1, altitude_degrees=0.0)
    windows = []
    rise_time = None

    # Determine local timezone based on latitude and longitude
    local_timezone = pytz.timezone(determine_timezone(latitude, longitude))

    for time, event in zip(times, events):
        if event == 0:  # Satellite rises
            rise_time = time.utc_datetime().astimezone(local_timezone)  # Convert to local time zone
        elif event == 2 and rise_time:  # Satellite sets
            set_time = time.utc_datetime().astimezone(local_timezone)  # Convert to local time zone
            windows.append((rise_time, set_time))
            rise_time = None

    # # Printing the viewing windows in local timezone
    # for window in windows:
    #     print(f"Viewing window for {satellite.name}: from {window[0]} to {window[1]} in timezone {local_timezone.zone}")

    return windows

def determine_timezone(latitude, longitude):
    tf = TimezoneFinder()
    return tf.timezone_at(lat=latitude, lng=longitude)

def get_non_overlapping_non_repeating_schedule(satellites, start_time, end_time, latitude, longitude, topos):
    # Fetch all viewing windows for all satellites
    all_windows = []
    for satellite in satellites:
        for window in get_all_viewing_windows(satellite, start_time, end_time, topos, latitude, longitude):
            all_windows.append((satellite.name, window[0], window[1], satellite))

    # Sort the windows by their start time
    all_windows.sort(key=lambda x: x[1])

    last_set_time = None
    seen_satellites = set()  # To track satellites we've already seen

    non_overlapping_non_repeating_windows = []

    for sat_name, rise_time, set_time, satellite in all_windows:
        # Check if the window is non-overlapping and the satellite hasn't been seen before
        if (last_set_time is None or rise_time > last_set_time) and sat_name not in seen_satellites:
            non_overlapping_non_repeating_windows.append((sat_name, rise_time, set_time, satellite))
            last_set_time = set_time
            seen_satellites.add(sat_name)

    return non_overlapping_non_repeating_windows

def get_sequential_tracking_schedule(satellites, start_time, end_time, latitude, longitude, topos):
    # Initiate empty list to store the results
    tracking_schedule = []

    # Define the current end time as the start time
    current_end_time = start_time

    # Iterate over satellites based on their order
    for satellite in satellites:
        windows = get_all_viewing_windows(satellite, current_end_time, end_time, topos, latitude, longitude)

        # If there are windows available for the satellite
        if windows:
            rise_time, set_time = windows[0]  # We take the first available window
            tracking_schedule.append((satellite.name, rise_time, set_time, satellite))
            current_end_time = set_time  # Update the current end time to avoid overlap

    return tracking_schedule

def add_to_sequential_schedule(existing_schedule, satellites_to_add, start_time, end_time, latitude, longitude, topos):
    # If there's an existing schedule, pick the end time of the last satellite. Otherwise, use the start_time as the starting point.
    current_start_time = existing_schedule[-1][2] if existing_schedule else start_time

    # Iterate over the satellites to add
    for satellite in satellites_to_add:
        windows = get_all_viewing_windows(satellite, current_start_time, end_time, topos, latitude, longitude)

        # If there are windows available for the satellite
        if windows:
            rise_time, set_time = windows[0]  # We take the first available window
            existing_schedule.append((satellite.name, rise_time, set_time, satellite))
            current_start_time = set_time  # Update the current start time for the next satellite

    return existing_schedule

def get_azimuth_elevation(satellite, topos):
    
    # Load timescale object
    local_timezone = pytz.timezone(determine_timezone(latitude, longitude))

    # Create a timezone-aware datetime object
    aware_datetime = local_timezone.localize(datetime.now())

    # Convert the timezone-aware datetime to UTC
    utc_datetime = aware_datetime.astimezone(pytz.utc)

    # Convert the UTC datetime to a Time instance
    t = ts.utc(utc_datetime.year, utc_datetime.month, utc_datetime.day,
               utc_datetime.hour, utc_datetime.minute, utc_datetime.second)


    print(f"Current time: {t.utc_datetime()} in UTC")

    # Define observer's location
    observer_location = topos

    # Determine satellite's position at the given time
    sat_position = satellite.at(t)
    
    # Determine the difference between the satellite's position and the observer's location    
    difference = sat_position - observer_location.at(t)

    alt, az, _ = difference.altaz()

    return az.degrees, alt.degrees


def load_tle_from_string(tle_string):
    """
    Parse TLEs from a string and return the corresponding satellites.
    
    Parameters:
        tle_string (str): The TLE string containing one or multiple TLE entries.
    
    Returns:
        list: List of Satellite objects parsed from the TLE string.
    """
    lines = tle_string.strip().split("\n")
    satellites = []
    
    for i in range(0, len(lines), 3):
        name = lines[i].strip()
        line1 = lines[i+1].strip()
        line2 = lines[i+2].strip()
        satellite = EarthSatellite(line1, line2, name, load.timescale())
        satellites.append(satellite)
    
    return satellites


if __name__ == "__main__":
    tle_file = 'satellites.tle'
    

    latitude, longitude  = 37.2299995422363, -80.4179992675781
    local_timezone = pytz.timezone(determine_timezone(latitude, longitude))
    start_time = local_timezone.localize(datetime(2023, 9, 7, 0, 0))
    end_time = local_timezone.localize(datetime(2023, 9, 10, 23, 59))
    print(f"Timezone: {local_timezone}")

    topos = Topos(latitude_degrees=latitude, longitude_degrees=longitude, elevation_m=0)

    satellites = load.tle_file(tle_file)


    get_azimuth_elevation(satellites[0], topos)

    results = get_sequential_tracking_schedule(satellites, start_time, end_time, latitude, longitude, topos)
    for res in results:
        print(f"Satellite: {res[0]}")
        print(f"Viewing Time: From {res[1]} to {res[2]}")
        print(f"TLE:\n{res[3]}\n")
