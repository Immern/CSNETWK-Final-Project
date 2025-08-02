import sys
from lsnpy.core import LsnpPeer
from lsnpy.cli import LsnpCli
from lsnpy.handlers import LsnpMessageHandler

def main():
    try:
        if len(sys.argv) > 1:
            peer_username = sys.argv[1]
        else:
            peer_username = input("Enter your username: ").strip()

        # Create the message handler first
        message_handler = LsnpMessageHandler()
        
        # Instantiate the core peer, passing the message handler
        peer = LsnpPeer(username=peer_username, message_handler=message_handler)
        
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