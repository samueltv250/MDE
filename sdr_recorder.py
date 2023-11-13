import os
import numpy as np
import SoapySDR as sdr
from datetime import datetime
import threading
import logging
import pickle

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_BASE_DIR = "/mnt/usbdrive"

class SDRRecorder:
    DEFAULT_SAMPLE_RATE = 2e6
    BUFFER_SIZE = 2048 

    def __init__(self, device_args, mode='single', directory=DATA_BASE_DIR):
        if mode not in ['single', 'dual']:
            raise ValueError("Mode must be 'single' or 'dual'")
        self.device = sdr.Device(device_args)
        self.sample_rate = self.DEFAULT_SAMPLE_RATE
        self.streams = [None] * (2 if mode == 'dual' else 1)
        self.lock = threading.Lock()
        self.directory = directory

    def setup_device(self, channel, frequency, gain):
        with self.lock:
            try:
                self.device.setSampleRate(sdr.SOAPY_SDR_RX, channel, self.sample_rate)
                self.device.setFrequency(sdr.SOAPY_SDR_RX, channel, frequency)
                self.device.setGain(sdr.SOAPY_SDR_RX, channel, gain)
            except Exception as e:
                logger.error(f"Failed to setup device on channel {channel}: {e}")
                raise

    def activate_stream(self, channel):
        with self.lock:
            if self.streams[channel] is None:
                try:
                    self.streams[channel] = self.device.setupStream(sdr.SOAPY_SDR_RX, sdr.SOAPY_SDR_CF32, [channel])
                    self.device.activateStream(self.streams[channel])
                except Exception as e:
                    logger.error(f"Failed to activate stream on channel {channel}: {e}")
                    raise

    def record(self, channel, duration_seconds):
        num_samples = int(self.sample_rate * duration_seconds)
        buff = np.empty(self.BUFFER_SIZE, dtype=np.complex64)
        samples_collected = 0
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"SDR_Channel{channel}_{timestamp}.pkl"
        file_path = os.path.join(self.directory, filename)

        try:
            # with open(file_path, 'ab') as file:
            while samples_collected < num_samples:
                with self.lock:
                    sr = self.device.readStream(self.streams[channel], [buff], len(buff))
                    if sr.ret > 0:
                        # pickle.dump(buff[:sr.ret], file)
                        samples_collected += sr.ret
                        print(sr.ret)
                    elif sr.ret == sdr.SOAPY_SDR_TIMEOUT:
                        logger.warning("Read stream timeout.")
                    elif sr.ret == sdr.SOAPY_SDR_OVERFLOW:
                        logger.warning("Overflow occurred.")
                        break
                    elif sr.ret < 0:
                        logger.error(f"Stream error: {sr.ret}")
                        break
        except Exception as e:
            logger.error(f"Failed to record from channel {channel}: {e}")
            raise

    def start_recording(self, frequency, gain, duration_seconds):
        threads = []
        try:
            for channel in range(len(self.streams)):
                self.setup_device(channel, frequency, gain)
                self.activate_stream(channel)
                thread = threading.Thread(target=self.record, args=(channel, duration_seconds))
                threads.append(thread)
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        finally:
            # Deactivate and close streams after recording
            for channel in range(len(self.streams)):
                if self.streams[channel] is not None:
                    with self.lock:
                        self.device.deactivateStream(self.streams[channel])
                        self.device.closeStream(self.streams[channel])
                        self.streams[channel] = None
                        self.device.close()
            self.device = None  # Release the device



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




if dual_device_args:
    dual_tuner_recorder = SDRRecorder(dual_device_args, mode='dual')
    print("Starting dual tuner recording...")
    dual_tuner_recorder.start_recording(1.626e9, 30, 10)

# if single_device_args:
#     single_tuner_recorder = SDRRecorder(single_device_args, mode='single')
#     single_tuner_recorder.start_recording(1.626e9, 30, 120)
