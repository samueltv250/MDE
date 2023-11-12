# Raspberry Pi Setup for MDE Project

Ensure you use the provided Raspberry Pi image with SDRplay preloaded for the following steps.

## Preparing the Raspberry Pi Environment

1. Clone the project repository.
    cd Desktop && git clone https://github.com/samueltv250/MDE.git

2. Install required Python packages.
    pip install --break-system-packages skyfield && pip install --break-system-packages timezonefinder && pip install --break-system-packages pyserial && pip install --break-system-packages adafruit-circuitpython-gps

## Configuring Raspberry Pi as a Hotspot with Static IP Address

### Update and Upgrade DietPi
   sudo apt-get update && sudo apt-get upgrade -y

### Install Exfatprogs, Hostapd and Dnsmasq
   sudo apt-get install hostapd dnsmasq -y
   sudo apt-get install exfatprogs
### Stop Services to Configure Them
   sudo systemctl stop hostapd && sudo systemctl stop dnsmasq

### Configure Hostapd
1. Edit the configuration file.
   sudo nano /etc/hostapd/hostapd.conf
   *Add the following lines to the file:*
   interface=wlan0
   driver=nl80211
   ssid=SatelliteTrackingSystem
   hw_mode=g
   channel=7
   wmm_enabled=0
   auth_algs=1
   wpa=2
   wpa_passphrase=12345678
   wpa_key_mgmt=WPA-PSK
   wpa_pairwise=TKIP
   rsn_pairwise=CCMP

2. Point Hostapd to the Configuration File.
   sudo nano /etc/default/hostapd
   *Replace the #DAEMON_CONF line with:*
   DAEMON_CONF="/etc/hostapd/hostapd.conf"

### Configure Dnsmasq
1. Rename the original configuration file.
   sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig

2. Create a new configuration file.
   sudo nano /etc/dnsmasq.conf
   *Add the following lines to the file:*
   interface=wlan0
   dhcp-range=192.168.220.10,192.168.220.50,255.255.255.0,24h

### Set Static IP Address
1. Create a systemd service file.
   sudo nano /etc/systemd/system/static-ip-wlan0.service
   *Add the following lines to the file:*
   [Unit]
   Description=Set static IP address for wlan0
   Wants=network.target
   Before=network.target

   [Service]
   Type=oneshot
   ExecStart=/sbin/ip addr add 192.168.220.1/24 dev wlan0
   ExecStart=/sbin/ip link set wlan0 up
   RemainAfterExit=yes

   [Install]
   WantedBy=multi-user.target

2. Enable and start the service.
   sudo systemctl daemon-reload && sudo systemctl enable static-ip-wlan0 && sudo systemctl start static-ip-wlan0

### Start Hostapd and Dnsmasq
   sudo systemctl unmask hostapd && sudo systemctl enable hostapd && sudo systemctl start hostapd && sudo systemctl enable dnsmasq && sudo systemctl start dnsmasq

### Reboot the Raspberry Pi
   sudo reboot

### Improve Wireless Configuration
1. Call sudo dietpi-config.
2. Enable 802.11n/ac/ax.
3. Change Frequency to 5 GHz.

## Enabling slave.py at Boot

1. Create a New Service File.
   sudo nano /etc/systemd/system/slave.service
   *Add the following lines to the file:*
   [Unit]
   Description=Python Script Service
   After=network.target

   [Service]
   Type=simple
   User=dietpi
   WorkingDirectory=/home/dietpi/Desktop/MDE
   ExecStart=/usr/bin/python3 /home/dietpi/Desktop/MDE/slave.py
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target

2. Reload the System Daemon.
   sudo systemctl daemon-reload

3. Enable the Service.
   sudo systemctl enable slave.service

4. Start the Service.
   sudo systemctl start slave.service

5. Check the Service Status.
   sudo systemctl status slave.service


## Instructions to mount a USB drive on boot with the `dietpi` user as the owner:

1. Find the UUID of the USB Drive**:
   - Run the `blkid` command to find the UUID of your USB drive:
     ```sh
     sudo blkid
     ```
   - Look for the line that corresponds to your USB drive (`/dev/sda1` in this case) and note the `UUID`.

2. Create a Mount Point**:
   - Choose a location for your mount point, such as `/mnt/usbdrive`, and create it:
     ```sh
     sudo mkdir /mnt/usbdrive
     ```

3. Edit the `/etc/fstab` File**:
   - Open the `/etc/fstab` file in a text editor with root privileges:
     ```sh
     sudo nano /etc/fstab
     ```
   - Add the following line at the end of the file:
     ```
     UUID=your-uuid /mnt/usbdrive exfat uid=1000,gid=1000 0 2
     ```
     Replace `your-uuid` with the UUID you noted earlier.
     If your USB drive is not `exfat`, replace `exfat` with the actual filesystem type (e.g., `vfat` for FAT32, `ntfs-3g` for NTFS).

4. Mount the Drive**:
   - Now you can mount all drives with:
     ```sh
     sudo mount -a
     ```
   - This will apply all the new configurations set in the `/etc/fstab` file.

5. Set Ownership**:
   - Change the ownership of the mount point to `dietpi`:
     ```sh
     sudo chown dietpi:dietpi /mnt/usbdrive
     ```
   - This step is only necessary once, as the `fstab` entry will ensure the correct ownership on boot.

6. Test the Configuration**:
   - Reboot your Raspberry Pi to ensure the drive mounts automatically with the correct ownership:
     ```sh
     sudo reboot
     ```
   - After rebooting, verify that the drive is mounted and the ownership is correct with:
     ```sh
     ls -l /mnt/usbdrive
     ```

7. Troubleshooting**:
   - If you encounter any issues, you can revert the changes in `/etc/fstab` by commenting out the added line and rebooting the system. The backend will continue to operate without a drive but it will be limited to wireless offloading and less space.