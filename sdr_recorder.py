import os
import numpy as np
import SoapySDR as sdr
from datetime import datetime
import threading
import logging
import pickle
from queue import Queue
import time
import io
# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_BASE_DIR = "/mnt/usbdrive"

class SDRRecorder:
    DEFAULT_SAMPLE_RATE = 2e6
    BUFFER_SIZE = 1024*128

    def __init__(self, device_args, sat_name="NoName", frequency=1.626e9, mode='single', directory=DATA_BASE_DIR):
        self.device = sdr.Device(device_args)
        self.sample_rate = self.DEFAULT_SAMPLE_RATE
        self.mode = mode
        self.streams = [None] * (2 if mode == 'dual' else 1)
        self.lock = threading.Lock()
        self.directory = directory
        self.sat_name = sat_name
        self.frequency = frequency
        self.queues = [Queue() for _ in range(len(self.streams))]
        self.producer_threads = []
        self.consumer_threads = []

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

    def producer(self, channel, duration_seconds, queue):
        num_samples = int(self.sample_rate * duration_seconds)
        buff = np.empty(self.BUFFER_SIZE, dtype=np.complex64)
        samples_collected = 0

        while samples_collected < num_samples:
            with self.lock:
                sr = self.device.readStream(self.streams[channel], [buff], len(buff))
            if sr.ret > 0:
                queue.put(buff[:sr.ret].copy())
                samples_collected += sr.ret
            elif sr.ret == sdr.SOAPY_SDR_TIMEOUT:
                logger.warning("Read stream timeout.")
            elif sr.ret == sdr.SOAPY_SDR_OVERFLOW:
                logger.warning("Overflow occurred.")
            elif sr.ret < 0:
                logger.error(f"Stream error: {sr.ret}")

        # Signal the consumer that the production is done
        queue.put(None)
        print("finished one producer thread")

    def consumer(self, channel, queue):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{self.sat_name}_Frequency{self.frequency}_Channel{channel}_{timestamp}.pkl"
        file_path = os.path.join(self.directory, filename)
        with open(file_path, 'ab') as file:
            # Wrap the file with a BufferedWriter for more efficient writes
            buffered_writer = io.BufferedWriter(file)
            while True:
                data = queue.get()
                if data is None:  # Check for the sentinel value indicating the end of data
                    buffered_writer.flush()  # Flush any remaining data to disk
                    break
                print("dumping")
                pickle.dump(data, buffered_writer)  # Write data to the buffered writer
            buffered_writer.close()  # Close the buffer

    def start_recording(self, gain, duration_seconds):
        time.sleep(1)
        frequency = self.frequency
        for channel in range(len(self.streams)):
            self.setup_device(channel, frequency, gain)
            self.activate_stream(channel)

            # Start the producer thread
            producer_thread = threading.Thread(target=self.producer, args=(channel, duration_seconds, self.queues[channel]))
            producer_thread.start()
            self.producer_threads.append(producer_thread)

            # Start the consumer thread
            consumer_thread = threading.Thread(target=self.consumer, args=(channel, self.queues[channel]))
            consumer_thread.start()
            self.consumer_threads.append(consumer_thread)

    def stop_recording(self):
        # Wait for all producer threads to finish
        for thread in self.producer_threads:
            thread.join()

        # Wait for all consumer threads to finish
        for thread in self.consumer_threads:
            thread.join()

        # Deactivate and close all streams
        for channel in range(len(self.streams)):
            with self.lock:
                if self.streams[channel] is not None:
                    self.device.deactivateStream(self.streams[channel])
                    self.device.closeStream(self.streams[channel])
                    self.streams[channel] = None

        # Release the device
        self.device.close()
        self.device = None

# Example usage
devices = sdr.Device.enumerate()
single_device_args = None
dual_device_args = None

for dev in devices:
    if "Single Tuner" in dev["label"]:
        single_device_args = dev
    elif "Dual Tuner" in dev["label"]:
        dual_device_args = dev





if single_device_args:
    single_tuner_recorder = SDRRecorder(single_device_args, mode='single')
    single_tuner_recorder.start_recording(30, 30)
    single_tuner_recorder.stop_recording()

# if dual_device_args:
#     single_tuner_recorder = SDRRecorder(dual_device_args, mode='dual')
#     single_tuner_recorder.start_recording(30, 10)
#     single_tuner_recorder.stop_recording()

