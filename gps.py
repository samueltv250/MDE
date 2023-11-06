import time
import serial
import adafruit_gps

def init_gps():
    """Initialize the GPS module and return the GPS instance."""
    uart = serial.Serial(
        port='/dev/ttyS0',
        baudrate=9600,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1
    )
    
    gps = adafruit_gps.GPS(uart, debug=False)
    gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
    gps.send_command(b"PMTK220,1000")
    
    return gps

def get_coordinates(gps):
    """Get the current coordinates from the GPS module."""
    gps.update()
    
    if gps.has_fix:
        return gps.latitude, gps.longitude
    return None, None

if __name__ == "__main__":
    gps_instance = init_gps()
    
    while True:
        lat, lon = get_coordinates(gps_instance)
        if lat and lon:
            print(f"Latitude: {lat:.6f}, Longitude: {lon:.6f}")
        else:
            print("Waiting for fix...")
        time.sleep(1)