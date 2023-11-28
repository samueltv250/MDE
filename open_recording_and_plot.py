import numpy as np
import matplotlib.pyplot as plt
import os

def read_iq_samples(file_path):
    # Read the IQ samples from the file
    with open(file_path, 'rb') as file:
        raw_data = file.read()
    iq_samples = np.frombuffer(raw_data, dtype=np.complex64)
    return iq_samples


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


def plot_iq_samples(file_path, sample_rate=1e7, downsample_factor=100):
    # Read the IQ samples
    iq_samples = read_iq_samples(file_path)
    
    # Downsample the data by taking every nth sample
    iq_samples_downsampled = iq_samples[::downsample_factor]
    magnitude = np.abs(iq_samples_downsampled)
    phase = np.unwrap(np.angle(iq_samples_downsampled))
    
    # Compute the instantaneous frequency from downsampled data
    frequency = np.diff(phase) / (2.0 * np.pi) * (sample_rate / downsample_factor)
    
    # Create time axis for downsampled data
    time_axis = np.arange(len(iq_samples_downsampled)) * downsample_factor / sample_rate

    # Plot magnitude and frequency
    fig, axs = plt.subplots(2, 1, figsize=(10, 8))

    # Signal strength (Magnitude) over time
    axs[0].plot(time_axis, magnitude)
    axs[0].set_title('Signal Strength over Time')
    axs[0].set_xlabel('Time [s]')
    axs[0].set_ylabel('Magnitude')

    # Frequency over time - we lose one point due to diff operation
    axs[1].plot(time_axis[:-1], frequency)
    axs[1].set_title('Frequency over Time')
    axs[1].set_xlabel('Time [s]')
    axs[1].set_ylabel('Frequency [Hz]')

    plt.tight_layout()
    plt.show()

    
def prompt_directory_and_plot():
    # Ask the user for the directory path
    directory = input("Please enter the name of the file that is in the same directory as this script containing the IQ .dat files: ")


    plot_iq_samples(directory, sample_rate=10e6, downsample_factor=100000)

prompt_directory_and_plot()


