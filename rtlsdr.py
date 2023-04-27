from rtlsdr import RtlSdr
import matplotlib.pyplot as plt

# Configure RTL-SDR device
sdr = RtlSdr()
sdr.sample_rate = 2.0486e6  # Set sample rate (check valid sample rates first!)
sample_rate = sdr.sample_rate  # Store sample rate as a separate variable
sdr.center_freq = 1006e6  # Set center frequency
center_freq = sdr.center_freq
sdr.gain = 0  # Set gain (use caution not to burn the SDR; use "auto' for automatic gain control)

# Close existing plots (fixes bug showing old plots)
plt.close()

# Receive samples
number_of_samples = int(sample_rate)  # Receive samples for 1 second
samples = sdr.read_samples(number_of_samples)

# Close RTL-SDR device
sdr.close()

# Print raw I/Q samples
print(samples)
