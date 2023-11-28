import numpy as np
import matplotlib.pyplot as plt
import os
import re


def read_iq_samples_chunked(file_path, chunk_size=1024*1024):
    # Read the IQ samples from the file in chunks
    iq_samples = []
    with open(file_path, 'rb') as file:
        while True:
            raw_data = file.read(chunk_size)
            if not raw_data:
                break
            # Convert the bytes to complex64
            iq_samples_chunk = np.frombuffer(raw_data, dtype=np.complex64)
            # Process the chunk (for example, just append to a list here)
            iq_samples.append(iq_samples_chunk)
    # Combine chunks into one array if needed
    iq_samples = np.concatenate(iq_samples)
    return iq_samples


class IQDataProcessor:
    def __init__(self, filepath):
        self.filepath = filepath
        self.parse_filename()

    def parse_filename(self):
        # Extract parameters from the filename using a regular expression
        filename_pattern = r"(.+)_Frequency(\d+)_SampleRate(\d+)_Channel(\d+)_(.+)\.dat"
        match = re.search(filename_pattern, os.path.basename(self.filepath))
        if match:
            self.sat_name = match.group(1)
            self.frequency = int(match.group(2))
            self.sample_rate = int(match.group(3))
            self.channel = int(match.group(4))
            self.timestamp = match.group(5)
        else:
            raise ValueError("Filename does not match the expected format.")

    def read_iq_samples(self):
        # Read the IQ samples from the file
        with open(self.filepath, 'rb') as file:
            raw_data = file.read()
        iq_samples = np.frombuffer(raw_data, dtype=np.complex64)
        return iq_samples

    def compute_spectrum(self, iq_samples, fft_size=1024):
        # Compute the spectrum of the IQ samples
        spectrum = np.abs(np.fft.fftshift(np.fft.fft(iq_samples, n=fft_size))) / fft_size
        frequency_axis = np.fft.fftshift(np.fft.fftfreq(fft_size, d=1/self.sample_rate))
        return frequency_axis, spectrum

    def plot_signal_strength_and_spectrum(self, fft_size=1024):
        # Read the IQ samples
        iq_samples = self.read_iq_samples()
        
        # Compute the signal strength (magnitude)
        signal_strength = np.abs(iq_samples)
        
        # Compute the spectrum
        frequency_axis, spectrum = self.compute_spectrum(iq_samples, fft_size=fft_size)
        
        # Average the spectrum if more than one FFT is computed
        averaged_spectrum = np.mean(spectrum.reshape(-1, fft_size), axis=0)

        # Create time axis for the signal strength
        time_axis = np.arange(len(signal_strength)) / self.sample_rate

        # Plot signal strength and averaged spectrum
        fig, axs = plt.subplots(2, 1, figsize=(10, 8))

        # Signal strength over time
        axs[0].plot(time_axis, signal_strength)
        axs[0].set_title('Signal Strength over Time')
        axs[0].set_xlabel('Time [s]')
        axs[0].set_ylabel('Magnitude')

        # Averaged spectrum over time
        axs[1].plot(frequency_axis, averaged_spectrum)
        axs[1].set_title('Averaged Spectrum')
        axs[1].set_xlabel('Frequency [Hz]')
        axs[1].set_ylabel('Amplitude')

        plt.tight_layout()
        plt.show()

def prompt_directory_and_plot():
    # Ask the user for the directory path
    directory = input("Please enter the name of the file containing the IQ .dat files: ")
    processor = IQDataProcessor(directory)
    processor.plot_signal_strength_and_spectrum(fft_size=1024)



    
if __name__ == "__main__":
    prompt_directory_and_plot()