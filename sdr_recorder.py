import os
import numpy as np
import SoapySDR as sdr
from datetime import datetime
import threading
import logging
from queue import Queue
import time

def align_buffer(byte_data, block_size=131072):
    """Pad the buffer to match the filesystem's block size for direct I/O"""
    buffer_size = byte_data.nbytes
    if buffer_size % block_size != 0:
        padding_size = block_size - (buffer_size % block_size)
        padding = np.zeros(padding_size, dtype=np.uint8)
        byte_data = np.concatenate((byte_data, padding))
    return byte_data.tobytes()



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_BASE_DIR = "/mnt/usbdrive"

class SDRRecorder:
    DEFAULT_SAMPLE_RATE = 2e6
    BUFFER_SIZE = 1000*100

    def __init__(self, device_args, sat_name="NoName", frequency=1.626e9, mode='single', directory=DATA_BASE_DIR, stop_event = threading.Event()):
        self.device = sdr.Device(device_args)
        self.sample_rate = self.DEFAULT_SAMPLE_RATE
        self.mode = mode
        self.streams = [None] * (2 if mode == 'dual' else 1)
        self.lock = threading.Lock()
        self.directory = directory
        self.sat_name = sat_name
        self.frequency = frequency
        self.queues = [Queue(maxsize=10000) for _ in range(len(self.streams))]
        self.producer_threads = []
        self.consumer_threads = []
        self.stop_event = stop_event

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
      
        while samples_collected < num_samples and not self.stop_event.set():
            with self.lock:
                sr = self.device.readStream(self.streams[channel], [buff], len(buff))
            if sr.ret > 0:
                while True:
                    try:
                        queue.put(buff[:sr.ret], block = True, timeout = 5)
                        break
                    except:
                        print("queue is full")
                samples_collected += sr.ret
            elif sr.ret == sdr.SOAPY_SDR_TIMEOUT:
                logger.warning("Read stream timeout.")
            elif sr.ret == sdr.SOAPY_SDR_OVERFLOW:
                logger.warning("Overflow occurred.")
            elif sr.ret < 0:
                logger.error(f"Stream error: {sr.ret}")

        # Signal the consumer that the production is done
        queue.put(None)
        print("finished producer thread")

    def consumer(self, channel, queue):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{self.sat_name}_Frequency{self.frequency}_Channel{channel}_{timestamp}.dat"
        file_path = os.path.join(self.directory, filename)
        block_size = 131072  
        
        # Open the file with os.open() to get a file descriptor with direct I/O flags
        fd = os.open(file_path, os.O_WRONLY | os.O_CREAT, 0o660)
        
        try:
            while True:
                data = queue.get()
                if data is None:  # Check for the sentinel value indicating the end of data
                    break
                
                # Convert the complex64 data to bytes
                byte_data = data.view(np.uint8)
                # byte_data = data.tobytes()
       
                # Ensure the buffer is correctly aligned for direct I/O
                aligned_data = align_buffer(byte_data, block_size)
                
                # Write the aligned data to the file using the file descriptor
                os.write(fd, aligned_data)
        finally:
            # Use fsync to ensure all internal file buffers are written to disk
            os.fsync(fd)
            # Close the file descriptor
            os.close(fd)



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
        self.stop_event.set()
        
        # Wait for all consumer threads to finish
        for thread in self.consumer_threads:
            thread.join()
 
        import gc
        gc.collect()



if __name__ == "__main__":
    # Example usage
    devices = sdr.Device.enumerate()
    single_device_args = None
    dual_device_args = None

    for dev in devices:
        if "Single Tuner" in dev["label"]:
            single_device_args = dev
        elif "Dual Tuner" in dev["label"]:
            dual_device_args = dev




    start_time = time.perf_counter()
    if single_device_args:
        single_tuner_recorder = SDRRecorder(single_device_args, mode='single')
        single_tuner_recorder.start_recording(30, 300)
        single_tuner_recorder.stop_recording()


    end = time.perf_counter()

    print(end-start_time)




    # start_time = time.perf_counter()
    # if dual_device_args:
    #     single_tuner_recorder = SDRRecorder(dual_device_args, mode='dual')
    #     single_tuner_recorder.start_recording(30, 10)
    #     single_tuner_recorder.stop_recording()


    # end = time.perf_counter()

    # print(end-start_time)


