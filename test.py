import os
import pickle
import numpy as np
import SoapySDR as sdr
from datetime import datetime, timedelta
DATA_BASE_DIR = "/home/dietpi/Desktop/MDE/data_base"

def record(sdr_device, frequency, gain, sample_rate, duration_seconds):




    # Set up the SDR device parameters
    sdr_device.setSampleRate(sdr.SOAPY_SDR_RX, 0, sample_rate)
    sdr_device.setFrequency(sdr.SOAPY_SDR_RX, 0, frequency)
    sdr_device.setGain(sdr.SOAPY_SDR_RX, 0, gain)

    # Create a stream
    rx_stream = sdr_device.setupStream(sdr.SOAPY_SDR_RX, sdr.SOAPY_SDR_CF32)
    sdr_device.activateStream(rx_stream)

    # Calculate the total number of samples to capture
    num_samples = int(sample_rate * duration_seconds)

    # Create a buffer to hold the samples
    buffer_size = 65536
    buff = np.empty(buffer_size, dtype=np.complex64)

    # Determine the filename based on the current time
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"SDR_{frequency}Hz_{timestamp}.pkl"
    file_path = os.path.join(DATA_BASE_DIR, filename)

    # Open the file for writing
    with open(file_path, 'ab') as file:
        samples_collected = 0
        while samples_collected < num_samples:
            # Read samples from the device
            sr = sdr_device.readStream(rx_stream, [buff], buffer_size)
            if sr.ret > 0:
                # Store samples in the file
                # pickle.dump(buff[:sr.ret], file)
                samples_collected += sr.ret
            elif sr.ret == -1:
                # Overflow has occurred
                print("Overflow occurred")
                break

    # Deactivate and close the stream
    sdr_device.deactivateStream(rx_stream)
    sdr_device.closeStream(rx_stream)


devices = sdr.Device.enumerate()
for dev in devices:
    print(dev)
    if dev["label"].strip() == "SDRplay Dev0 RSPduo 230102CE34 - Single Tuner":
        single_device_args = dev
    elif dev["label"].strip() == "SDRplay Dev1 RSPduo 230102CE34 - Dual Tuner":
        dual_device_args = dev

# Example usage:
mainSdr = sdr.Device(single_device_args) # Initialize your SoapySDR Device here
frequency = 1.626e9  # Frequency in Hz
gain = 30  # Gain in dB
sample_rate = 2e6  # Sample rate in samples per second
duration_seconds = 120  # Duration of recording in seconds
record(mainSdr, frequency, gain, sample_rate, duration_seconds)