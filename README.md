To enable autopairing with the **autopair.service**, follow the steps below in the Raspberry pi terminal:

## Installation:

1. **Reload Configuration**: 
    - Run the command below to update the systemd manager configuration:
    ```bash
    sudo systemctl daemon-reload
    ```

2. **Enable Boot Start**: 
    - To ensure the service starts upon boot, run:
    ```bash
    sudo systemctl enable autopair.service
    ```

3. **Start Service**: 
    - To start the service immediately without a reboot, use:
    ```bash
    sudo systemctl start autopair.service
    ```

## Precaution:
- Before initiating the service, ensure the Python script `/home/pi/auto_pair_agent.py` is available and accessible.
