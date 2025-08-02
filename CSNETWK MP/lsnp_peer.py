import socket
import threading
import time
import sys
import uuid

# LSNP Constants
PORT = 50999
# Use '<broadcast>' for the broadcast address, which is a platform-independent
# way to send to the broadcast address.
BROADCAST_ADDR = '<broadcast>'

class LsnpPeer:
    """
    Implements the core functionality for a peer in the Local Social Networking Protocol.
    This class handles network communication, message parsing, and user interaction.
    """

    def __init__(self, username):
        """
        Initializes the LSNP peer.

        Args:
            username (str): The display name for this user.
        """
        if not username:
            raise ValueError("Username cannot be empty.")

        self.username = username
        self.verbose = False
        self.running = True

        # Data stores for received messages
        self.known_peers = {} # Maps user_id to peer data
        self.posts = []
        self.dms = []

        # Set up the UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Allow reusing the address, helpful for quick restarts
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Enable broadcasting
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Bind to the LSNP port on all available interfaces
        self.socket.bind(('', PORT))
        # Set a timeout so the listening loop doesn't block forever
        self.socket.settimeout(1.0)

        # Determine the user's local IP to create the USER_ID
        self.ip_address = self._get_local_ip()
        self.user_id = f"{self.username}@{self.ip_address}"

        print(f"LSNP Peer '{self.username}' initialized.")
        print(f"Your USER_ID is: {self.user_id}")
        print(f"Listening on port {PORT}...")


    def _get_local_ip(self):
        """
        Finds the local IP address of the machine.
        This is a helper function to construct the USER_ID.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't have to be reachable
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def start(self):
        """
        Starts the peer's operation by launching listener and command threads.
        """
        print("\nStarting LSNP Peer... Type 'help' for a list of commands.")
        # Thread for listening to incoming messages
        listener_thread = threading.Thread(target=self._listen, daemon=True)
        listener_thread.start()

        # The main thread will handle the command loop
        self._command_loop()

    def stop(self):
        """
        Stops the peer and cleans up resources.
        """
        print("\nShutting down LSNP Peer...")
        self.running = False
        self.socket.close()
        print("Shutdown complete.")

    def _listen(self):
        """
        Continuously listens for incoming UDP messages.
        This method is intended to be run in a separate thread.
        """
        while self.running:
            try:
                # Wait for a message
                data, addr = self.socket.recvfrom(4096) # 4KB buffer size
                if data:
                    self._handle_message(data, addr)
            except socket.timeout:
                # No data received, just continue the loop
                continue
            except Exception as e:
                if self.running:
                    print(f"[ERROR] An error occurred in the listener: {e}")
                break

    def _handle_message(self, data, addr):
        """
        Processes a received message after it's been received by the listener.

        Args:
            data (bytes): The raw message data.
            addr (tuple): The address (ip, port) of the sender.
        """
        try:
            message_str = data.decode('utf-8')
            parsed_message = self._parse_message(message_str)

            if self.verbose:
                print("\n--- RECV ---")
                print(f"From: {addr}")
                print(f"Raw: {message_str.strip()}")
                print(f"Parsed: {parsed_message}")
                print("------------")

            # Basic routing based on message type
            msg_type = parsed_message.get('TYPE')
            if msg_type == 'PROFILE':
                user_id = parsed_message.get('USER_ID')
                if user_id:
                    self.known_peers[user_id] = parsed_message
            elif msg_type == 'POST':
                self.posts.append(parsed_message)
            elif msg_type == 'DM':
                # Only store DMs addressed to this user
                if parsed_message.get('TO') == self.user_id:
                    self.dms.append(parsed_message)
            # Other message types will be handled in later milestones
            # but are parsed correctly here.

        except (UnicodeDecodeError, ValueError) as e:
            print(f"\n[ERROR] Could not process message from {addr}: {e}")

    def _parse_message(self, message_str):
        """
        Parses a raw LSNP message string into a dictionary.

        Args:
            message_str (str): The complete message string.

        Returns:
            dict: A dictionary representing the key-value pairs of the message.
        """
        if not message_str.endswith('\n\n'):
            raise ValueError("Message format invalid: does not end with a blank line.")

        message_dict = {}
        lines = message_str.strip().split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # Handle multi-line data for fields like AVATAR_DATA
                if key == 'AVATAR_DATA':
                    data_lines = [value]
                    i += 1
                    while i < len(lines) and ':' not in lines[i]:
                        data_lines.append(lines[i])
                        i += 1
                    message_dict[key] = '\n'.join(data_lines)
                    continue # Continue to the next key-value pair
                else:
                    message_dict[key] = value
            i += 1
        return message_dict

    def _format_message(self, payload):
        """
        Formats a dictionary payload into a valid LSNP message string.

        Args:
            payload (dict): The dictionary of key-value pairs to format.

        Returns:
            str: A formatted LSNP message string.
        """
        message_parts = []
        for key, value in payload.items():
            message_parts.append(f"{key}: {value}")
        # Join with newlines and add the required trailing blank line
        return '\n'.join(message_parts) + '\n\n'

    def _send_message(self, payload, destination_addr):
        """
        Formats and sends a message to a given destination.

        Args:
            payload (dict): The message payload.
            destination_addr (tuple or str): The destination address.
                                             Can be ('ip', port) or '<broadcast>'.
        """
        try:
            message_str = self._format_message(payload)
            message_bytes = message_str.encode('utf-8')

            if destination_addr == BROADCAST_ADDR:
                self.socket.sendto(message_bytes, (BROADCAST_ADDR, PORT))
                if self.verbose:
                    print("\n--- SENT (Broadcast) ---")
                    print(message_str.strip())
                    print("------------------------")
            else:
                self.socket.sendto(message_bytes, destination_addr)
                if self.verbose:
                    print(f"\n--- SENT (Unicast to {destination_addr}) ---")
                    print(message_str.strip())
                    print("---------------------------------------")

        except Exception as e:
            print(f"\n[ERROR] Could not send message: {e}")

    def _command_loop(self):
        """
        Handles user input from the command line to drive the peer's actions.
        """
        while self.running:
            try:
                # Prompt user for input
                cmd_input = input(f"\n({self.username}) > ").strip()
                if not cmd_input:
                    continue

                parts = cmd_input.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                # --- Command Handling ---
                if command == 'quit':
                    self.running = False
                elif command == 'help':
                    self._print_help()
                elif command == 'verbose':
                    self.verbose = not self.verbose
                    print(f"Verbose mode is now {'ON' if self.verbose else 'OFF'}.")
                elif command == 'profile':
                    self._send_profile_command(args)
                elif command == 'post':
                    self._send_post_command(args)
                elif command == 'dm':
                    self._send_dm_command(args)
                elif command == 'peers':
                    self._print_peers()
                elif command == 'posts':
                    self._print_posts()
                elif command == 'dms':
                    self._print_dms()
                else:
                    print(f"Unknown command: '{command}'. Type 'help' for a list of commands.")

            except (KeyboardInterrupt, EOFError):
                self.running = False
            except Exception as e:
                print(f"[ERROR] An error occurred in the command loop: {e}")

    # --- Command Implementations ---

    def _print_help(self):
        print("\n--- LSNP Client Commands ---")
        print("profile <status>             - Broadcast your profile with a new status.")
        print("post <content>               - Broadcast a public post.")
        print("dm <user_id> <message>       - Send a direct message to a user.")
        print("peers                        - List all known peers on the network.")
        print("posts                        - Show all received public posts.")
        print("dms                          - Show all received direct messages for you.")
        print("verbose                      - Toggle detailed message logging ON/OFF.")
        print("help                         - Show this help message.")
        print("quit                         - Shut down the client.")
        print("--------------------------")

    def _send_profile_command(self, args):
        if not args:
            print("Usage: profile <status>")
            return
        payload = {
            'TYPE': 'PROFILE',
            'USER_ID': self.user_id,
            'DISPLAY_NAME': self.username,
            'STATUS': args
        }
        self._send_message(payload, BROADCAST_ADDR)
        print("Profile broadcasted.")

    def _send_post_command(self, args):
        if not args:
            print("Usage: post <content>")
            return
        payload = {
            'TYPE': 'POST',
            'USER_ID': self.user_id,
            'CONTENT': args,
            'MESSAGE_ID': uuid.uuid4().hex[:16], # Example message ID
            'TIMESTAMP': int(time.time()),
            'TTL': 3600
        }
        self._send_message(payload, BROADCAST_ADDR)
        print("Post broadcasted.")

    def _send_dm_command(self, args):
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: dm <user_id> <message>")
            return
        recipient_id, message = parts
        
        # Find recipient IP from known peers
        recipient_ip = None
        if '@' in recipient_id:
             recipient_ip = recipient_id.split('@')[1]
        
        if not recipient_ip:
            print(f"Error: Could not determine IP for '{recipient_id}'. Make sure they have sent a profile message.")
            return

        payload = {
            'TYPE': 'DM',
            'FROM': self.user_id,
            'TO': recipient_id,
            'CONTENT': message,
            'MESSAGE_ID': uuid.uuid4().hex[:16],
            'TIMESTAMP': int(time.time())
        }
        self._send_message(payload, (recipient_ip, PORT))
        print(f"DM sent to {recipient_id}.")

    def _print_peers(self):
        print("\n--- Known Peers ---")
        if not self.known_peers:
            print("No peers discovered yet. Wait for a PROFILE message.")
        else:
            for user_id, data in self.known_peers.items():
                name = data.get('DISPLAY_NAME', 'N/A')
                status = data.get('STATUS', 'N/A')
                print(f"- {name} ({user_id}): {status}")
        print("-------------------")

    def _print_posts(self):
        print("\n--- Public Posts ---")
        if not self.posts:
            print("No posts received yet.")
        else:
            for i, post in enumerate(self.posts):
                sender = post.get('USER_ID', 'Unknown')
                content = post.get('CONTENT', '')
                print(f"{i+1}. From {sender}: {content}")
        print("--------------------")

    def _print_dms(self):
        print("\n--- Direct Messages for You ---")
        if not self.dms:
            print("No DMs received yet.")
        else:
            for i, dm in enumerate(self.dms):
                sender = dm.get('FROM', 'Unknown')
                content = dm.get('CONTENT', '')
                print(f"{i+1}. From {sender}: {content}")
        print("-------------------------------")


if __name__ == "__main__":
    # Entry point of the script
    try:
        # Get username from command line argument or prompt the user
        if len(sys.argv) > 1:
            peer_username = sys.argv[1]
        else:
            peer_username = input("Enter your username: ").strip()

        peer = LsnpPeer(username=peer_username)
        peer.start() # This will block until the user quits

    except ValueError as e:
        print(f"[FATAL] {e}")
    except KeyboardInterrupt:
        print("\nUser interrupted. Shutting down.")
    finally:
        # The stop method is called within the command loop on 'quit' or Ctrl+C
        print("\nApplication has been terminated.")
