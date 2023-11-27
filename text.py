import os
import numpy as np
import SoapySDR as sdr
from datetime import datetime
import pickle
import threading


DATA_BASE_DIR = "/mnt/usbdrive"
class SDRRecorder:
    def __init__(self, device_args, mode='single', direc = "/mnt/usbdrive"):
        self.device = sdr.Device(device_args)
        self.mode = mode
        self.sample_rate = 2e6 if mode == 'dual' else  10e6
        self.streams = [None, None] if mode == 'dual' else [None]  # Adjusted for mode
        self.lock = threading.Lock()
        self.is_initialized = False
        self.dir = direc
        

    def setup_device(self, channel, frequency, gain):
        with self.lock:
            self.device.setSampleRate(sdr.SOAPY_SDR_RX, channel, self.sample_rate)
            self.device.setFrequency(sdr.SOAPY_SDR_RX, channel, frequency)
            self.device.setGain(sdr.SOAPY_SDR_RX, channel, gain)

    def activate_stream(self, channel):
        with self.lock:
            if self.streams[channel] is None:
                self.streams[channel] = self.device.setupStream(sdr.SOAPY_SDR_RX, sdr.SOAPY_SDR_CF32, [channel])
                self.device.activateStream(self.streams[channel])

    def record(self, channel, duration_seconds):
        print("starting")
        with self.lock:
            rx_stream = self.streams[channel]
        num_samples = int(self.sample_rate * duration_seconds)
        buffer_size = 1024  # Smaller buffer size to avoid overflows
        buff = np.empty(buffer_size, dtype=np.complex64)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"SDR_Channel{channel}_{timestamp}.pkl"
        file_path = os.path.join(self.dir, filename)

        with open(file_path, 'ab') as file:
            samples_collected = 0
            while samples_collected < num_samples:
                with self.lock:
                    sr = self.device.readStream(rx_stream, [buff], buffer_size)
                    # self.device.releaseReadBuffer(rx_stream, sr.ret)
                if sr.ret > 0:
                    
                    # pickle.dump(buff[:sr.ret], file)
                    print(sr.ret)
                    samples_collected += sr.ret
                elif sr.ret == -1:
                    print("Overflow occurred")
                    break

    def start_recording(self, frequency, gain, duration_seconds):
        for channel in range(len(self.streams)):
            self.setup_device(channel, frequency, gain)
            self.activate_stream(channel)

        # Recording in a sequential manner to avoid thread issues
        threads = []
        for channel in range(len(self.streams)):
            threads.append(threading.Thread(target=self.record, args=(channel, duration_seconds)))
        
        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Deactivate and close streams after recording
        for channel, stream in enumerate(self.streams):
            if stream is not None:
                self.device.deactivateStream(stream)
                self.device.closeStream(stream)
                self.device.close()




# Example usage
devices = sdr.Device.enumerate()
single_device_args = None
dual_device_args = None

for dev in devices:
    print(dev)
    if "Single Tuner" in dev["label"]:
        single_device_args = dev
    elif "Dual Tuner" in dev["label"]:
        dual_device_args = dev




# if dual_device_args:
#     dual_tuner_recorder = SDRRecorder(dual_device_args, mode='dual')
#     dual_tuner_recorder.start_recording(1.626e9, 30, 10)

if single_device_args:
    single_tuner_recorder = SDRRecorder(single_device_args, mode='single')
    single_tuner_recorder.start_recording(1.626e9, 30, 120)