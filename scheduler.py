from skyfield.api import Topos, load, EarthSatellite, wgs84
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder

ts = load.timescale()

def determine_timezone(latitude, longitude):
    tf = TimezoneFinder()
    return tf.timezone_at(lat=latitude, lng=longitude)

def get_all_viewing_windows(satellite, start_time, end_time, observer_location):
    # This function was tested with publicly available tracking software and the results match.
    # Software link: https://dl2rum.de/rotor/docs/en/pages/WinSats.html
    if start_time.tzinfo is None or start_time.tzinfo.utcoffset(start_time) is None:
        raise ValueError("start_time must be timezone-aware")
    if end_time.tzinfo is None or end_time.tzinfo.utcoffset(end_time) is None:
        raise ValueError("end_time must be timezone-aware")

    start_time_utc = start_time.astimezone(pytz.utc)
    end_time_utc = end_time.astimezone(pytz.utc)

    t0 = ts.utc(start_time_utc.year, start_time_utc.month, start_time_utc.day, start_time_utc.hour, start_time_utc.minute, start_time_utc.second)
    t1 = ts.utc(end_time_utc.year, end_time_utc.month, end_time_utc.day, end_time_utc.hour, end_time_utc.minute, end_time_utc.second)

    times, events = satellite.find_events(observer_location, t0, t1)
    windows = []
    rise_time = None

    # Determine local timezone directly based on latitude and longitude
    local_timezone = pytz.timezone(determine_timezone(observer_location.latitude.degrees, observer_location.longitude.degrees))

    for time, event in zip(times, events):
        if event == 0:  # Satellite rises
            rise_time = time.utc_datetime().astimezone(local_timezone)  # Convert to local time zone
        elif event == 2 and rise_time:  # Satellite sets
            set_time = time.utc_datetime().astimezone(local_timezone)  # Convert to local time zone
            windows.append((rise_time, set_time))
            rise_time = None

    for window in windows:
        print(f"Viewing window for {satellite.name}: from {window[0].strftime('%Y-%m-%d %H:%M:%S')} to {window[1].strftime('%Y-%m-%d %H:%M:%S')} in timezone {window[0].tzinfo.zone}")

    return windows



def get_non_overlapping_non_repeating_schedule(satellites, start_time, end_time, topos):
    # Fetch all viewing windows for all satellites
    all_windows = []
    for satellite in satellites:
        for window in get_all_viewing_windows(satellite, start_time, end_time, topos):
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

def get_sequential_tracking_schedule(satellites, start_time, end_time, topos):
    empty_sats = []
    return add_to_sequential_schedule(empty_sats,satellites, start_time, end_time, topos)

def add_to_sequential_schedule(existing_schedule, satellites_to_add, start_time, end_time, topos):
    # If there's an existing schedule, pick the end time of the last satellite. Otherwise, use the start_time as the starting point.
    current_start_time = existing_schedule[-1][2] if len(existing_schedule) > 0 else start_time
    new_schedule = []

    # Iterate over the satellites to add
    for satellite in satellites_to_add:
        windows = get_all_viewing_windows(satellite, current_start_time, end_time, topos)
        
        # Sort the windows based on the rise time
        sorted_windows = sorted(windows, key=lambda x: x[0])

        # If there are windows available for the satellite
        for rise_time, set_time in sorted_windows:
            # Ensure the rise time is after the last set time from the existing schedule
            if not existing_schedule or rise_time > existing_schedule[-1][2]:
                new_schedule.append((satellite.name, rise_time, set_time, satellite))
                current_start_time = set_time  # Update the current start time for the next satellite
                break  # Break after scheduling the first non-overlapping window

    return existing_schedule + new_schedule


def get_azimuth_elevation(satellite, observer_location):
    # This function was tested with publicly available tracking software and the results match.
    # Software link: https://dl2rum.de/rotor/docs/en/pages/WinSats.html

    # Get the current UTC time
    utc_datetime = datetime.utcnow()

    # Convert the current time to a Time instance
    t = ts.utc(utc_datetime.year, utc_datetime.month, utc_datetime.day,
               utc_datetime.hour, utc_datetime.minute, utc_datetime.second)

    # Compute the satellite's position relative to the observer's location
    difference = satellite - observer_location
    topocentric = difference.at(t)

    # Compute altazimuth (azimuth, elevation) coordinates
    alt, az, d = topocentric.altaz()

    return az.degrees, alt.degrees



def load_tle_from_string(tle_string):
    lines = tle_string.strip().split("\n")
    satellites = []
    
    for i in range(0, len(lines), 3):
        name = lines[i].strip()
        line1 = lines[i+1].strip()
        line2 = lines[i+2].strip()
        satellite = EarthSatellite(line1, line2, name, load.timescale())
        satellites.append(satellite)
    
    return satellites

