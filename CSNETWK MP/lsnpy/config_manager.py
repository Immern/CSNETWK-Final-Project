"""
A module to manage network configuration, allowing for easy switching
between original (multi-device) and simulated (single-device) modes.
"""

def get_network_config(mode, ip_address):
    """
    Returns the network configuration based on the requested mode.

    Args:
        mode (str): 'original' for multi-device or 'simulate' for single-device.
        ip_address (str): The specific IP address to use for 'simulate' mode.

    Returns:
        dict: A dictionary containing the 'bind_ip' and 'mode'.
    """
    if mode == 'original':
        # In original mode, we bind to all interfaces to listen for
        # traffic from other devices on the network.
        return {
            'bind_ip': '',
            'mode': 'original'
        }
    elif mode == 'simulate':
        # In simulate mode, we use the provided IP address to create a
        # virtual network endpoint on the local machine.
        if not ip_address:
            raise ValueError("An IP address must be provided for 'simulate' mode.")
        return {
            'bind_ip': ip_address,
            'mode': 'simulate'
        }
    else:
        raise ValueError(f"Unknown mode: {mode}. Please use 'original' or 'simulate'.")
