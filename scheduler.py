from skyfield.api import Topos, load
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder

def get_all_viewing_windows(satellite, start_time, end_time, topos, latitude, longitude):
    ts = load.timescale()
    t0 = ts.utc(start_time.year, start_time.month, start_time.day, start_time.hour, start_time.minute, start_time.second)
    t1 = ts.utc(end_time.year, end_time.month, end_time.day, end_time.hour, end_time.minute, end_time.second)

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

def get_shortest_viewing_schedule(tle_file, start_time, end_time, latitude, longitude):
    satellites = load.tle_file(tle_file)

    local_timezone = pytz.timezone(determine_timezone(latitude, longitude))
    start_time_local = local_timezone.localize(start_time)
    end_time_local = local_timezone.localize(end_time)

    start_time_utc = start_time_local.astimezone(pytz.utc)
    end_time_utc = end_time_local.astimezone(pytz.utc)

    topos = Topos(latitude_degrees=latitude, longitude_degrees=longitude, elevation_m=0)

    all_windows = []
    for satellite in satellites:
        for window in get_all_viewing_windows(satellite, start_time_utc, end_time_utc, topos, latitude, longitude):
            all_windows.append((satellite.name, window[0], window[1], satellite))

    # Sorting windows by their start time
    all_windows.sort(key=lambda x: x[1])

    # Only track each satellite once
    observed_satellites = set()
    unique_windows = []
    for window in all_windows:
        sat_name, _, _, _ = window
        if sat_name not in observed_satellites:
            observed_satellites.add(sat_name)
            unique_windows.append(window)

    return unique_windows


def get_non_overlapping_schedule(tle_file, start_time, end_time, latitude, longitude):
    satellites = load.tle_file(tle_file)

    local_timezone = pytz.timezone(determine_timezone(latitude, longitude))
    start_time_local = local_timezone.localize(start_time)
    end_time_local = local_timezone.localize(end_time)

    start_time_utc = start_time_local.astimezone(pytz.utc)
    end_time_utc = end_time_local.astimezone(pytz.utc)

    topos = Topos(latitude_degrees=latitude, longitude_degrees=longitude)

    all_windows = []
    for satellite in satellites:
        for window in get_all_viewing_windows(satellite, start_time_utc, end_time_utc, topos):
            all_windows.append((satellite.name, window[0], window[1], satellite))

    # Sorting windows by their start time
    all_windows.sort(key=lambda x: x[1])

    non_overlapping_windows = []
    last_set_time = None

    for sat_name, rise_time, set_time, satellite in all_windows:
        if last_set_time is None or rise_time > last_set_time:
            non_overlapping_windows.append((sat_name, rise_time, set_time, satellite))
            last_set_time = set_time

    return non_overlapping_windows

if __name__ == "__main__":
    tle_file = 'satellites.tle'
    start_time = datetime(2023, 9, 7, 0, 0)
    end_time = datetime(2023, 9, 10, 23, 59)
    latitude, longitude  = 37.2299995422363, -80.4179992675781
    local_timezone = pytz.timezone(determine_timezone(latitude, longitude))
    print(f"Timezone: {local_timezone}")

    results = get_shortest_viewing_schedule(tle_file, start_time, end_time, latitude, longitude)
    for res in results:
        print(f"Satellite: {res[0]}")
        print(f"Viewing Time: From {res[1]} to {res[2]}")
        print(f"TLE:\n{res[3]}\n")
