import sys
import argparse
from lsnpy.core import LsnpPeer
from lsnpy.cli import LsnpCli
from lsnpy.handlers import LsnpMessageHandler
from lsnpy.config_manager import get_network_config # Import the new module

def main():
    # Use argparse to handle command-line arguments
    parser = argparse.ArgumentParser(description="LSNP Client")
    parser.add_argument('username', type=str, nargs='?', help='The username for this peer.')
    parser.add_argument('--mode', type=str, default='original', choices=['original', 'simulate'], help='Network mode: "original" for multi-device, "simulate" for single-device testing.')
    parser.add_argument('--ip', type=str, help='Required for simulate mode. Use a unique IP like 127.0.0.1 or 127.0.0.2.')
    args = parser.parse_args()
    
    try:
        # Get username from args or prompt the user
        if args.username:
            peer_username = args.username
        else:
            peer_username = input("Enter your username: ").strip()

        # Get network configuration based on mode and IP
        network_config = get_network_config(args.mode, args.ip)

        # Create the message handler first
        message_handler = LsnpMessageHandler()
        
        # Instantiate the core peer, passing the message handler and the bind IP
        peer = LsnpPeer(username=peer_username, message_handler=message_handler, bind_ip=network_config['bind_ip'])
        
        # Start the network threads
        peer.start_network_threads()

        # Create and start the command-line interface
        cli = LsnpCli(peer)
        cli.start_command_loop()

    except ValueError as e:
        print(f"[FATAL] {e}")
    except KeyboardInterrupt:
        print("\nUser interrupted. Shutting down.")
        
    
if __name__ == "__main__":
    main()
