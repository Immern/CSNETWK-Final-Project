import socket
import threading
import time
import sys
import uuid

# LSNP Constants
PORT = 50999
BROADCAST_ADDR = '<broadcast>'
PRESENCE_INTERVAL = 300 # 300 seconds = 5 minutes

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

        # Data stores
        self.known_peers = {} # Maps user_id to peer data
        self.posts = []
        self.dms = []
        self.followers = set() # Users who follow this peer
        self.following = set() # Users this peer follows

        # Set up the UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.bind(('', PORT))
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
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def start(self):
        """
        Starts the peer's operation by launching listener, presence, and command threads.
        """
        print("\nStarting LSNP Peer... Type 'help' for a list of commands.")
        
        # Thread for listening to incoming messages
        listener_thread = threading.Thread(target=self._listen, daemon=True)
        listener_thread.start()

        # Thread for broadcasting presence periodically
        presence_thread = threading.Thread(target=self._periodic_presence_broadcast, daemon=True)
        presence_thread.start()
        
        # Send an initial profile message to be discovered immediately
        self._send_profile_command(f"Hello! I'm {self.username}.")

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
        """
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                if data:
                    self._handle_message(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[ERROR] An error occurred in the listener: {e}")
                break
    
    def _periodic_presence_broadcast(self):
        """
        Periodically broadcasts a PING message to signal presence.
        This method is intended to be run in a separate thread.
        """
        while self.running:
            time.sleep(PRESENCE_INTERVAL)
            if self.running:
                payload = {
                    'TYPE': 'PING',
                    'USER_ID': self.user_id
                }
                self._send_message(payload, BROADCAST_ADDR)
                if self.verbose:
                    print("\n[INFO] Sent periodic PING broadcast.")


    def _handle_message(self, data, addr):
        """
        Processes a received message.
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

            msg_type = parsed_message.get('TYPE')
            sender_id = parsed_message.get('USER_ID') or parsed_message.get('FROM')

            if not sender_id:
                return # Ignore messages without a sender identifier

            # Route message based on type
            if msg_type == 'PROFILE':
                self.known_peers[sender_id] = parsed_message
            
            elif msg_type == 'PING':
                 # A peer has announced their presence. We can respond with our profile.
                if sender_id != self.user_id:
                    self._send_profile_command(f"Replying to PING from {sender_id}", destination_addr=addr)

            elif msg_type == 'POST':
                # Per RFC, only accept posts from users we follow.
                if sender_id in self.following or sender_id == self.user_id:
                    self.posts.append(parsed_message)
                    if self.verbose:
                        print(f"[INFO] Post from {sender_id} accepted (user is followed).")
                elif self.verbose:
                    print(f"[INFO] Post from {sender_id} ignored (user is not followed).")

            elif msg_type == 'DM':
                if parsed_message.get('TO') == self.user_id:
                    self.dms.append(parsed_message)
            
            elif msg_type == 'FOLLOW':
                if parsed_message.get('TO') == self.user_id:
                    self.followers.add(sender_id)
                    print(f"\n[Notification] {sender_id} is now following you.")
            
            elif msg_type == 'UNFOLLOW':
                if parsed_message.get('TO') == self.user_id:
                    self.followers.discard(sender_id)
                    print(f"\n[Notification] {sender_id} has unfollowed you.")

        except (UnicodeDecodeError, ValueError) as e:
            print(f"\n[ERROR] Could not process message from {addr}: {e}")

    def _parse_message(self, message_str):
        """
        Parses a raw LSNP message string into a dictionary.
        """
        if not message_str.strip().endswith('\n'):
            # A more robust check for the double newline
            if '\n\n' not in message_str:
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
                
                if key == 'AVATAR_DATA':
                    data_lines = [value]
                    i += 1
                    while i < len(lines) and ':' not in lines[i] and lines[i] != '':
                        data_lines.append(lines[i])
                        i += 1
                    message_dict[key] = '\n'.join(data_lines)
                    continue
                else:
                    message_dict[key] = value
            i += 1
        return message_dict

    def _format_message(self, payload):
        """
        Formats a dictionary payload into a valid LSNP message string.
        """
        message_parts = []
        for key, value in payload.items():
            message_parts.append(f"{key}: {value}")
        return '\n'.join(message_parts) + '\n\n'

    def _send_message(self, payload, destination_addr):
        """
        Formats and sends a message to a given destination.
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
        Handles user input from the command line.
        """
        while self.running:
            try:
                cmd_input = input(f"\n({self.username}) > ").strip()
                if not cmd_input:
                    continue

                parts = cmd_input.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                if command == 'quit':
                    self.running = False
                elif command == 'help':
                    self._print_help()
                elif command == 'verbose':
                    self.verbose = not self.verbose
                    print(f"Verbose mode is now {'ON' if self.verbose else 'OFF'}.")
                elif command == 'profile':
                    self._send_profile_command(args, BROADCAST_ADDR)
                elif command == 'post':
                    self._send_post_command(args)
                elif command == 'dm':
                    self._send_dm_command(args)
                elif command == 'follow':
                    self._send_follow_command(args)
                elif command == 'unfollow':
                    self._send_unfollow_command(args)
                elif command == 'peers':
                    self._print_peers()
                elif command == 'posts':
                    self._print_posts()
                elif command == 'dms':
                    self._print_dms()
                elif command == 'connections':
                    self._print_connections()
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
        print("post <content>               - Broadcast a public post to your followers.")
        print("dm <user_id> <message>       - Send a direct message to a user.")
        print("follow <user_id>             - Follow a user to receive their posts.")
        print("unfollow <user_id>           - Unfollow a user.")
        print("peers                        - List all known peers on the network.")
        print("posts                        - Show posts from users you follow.")
        print("dms                          - Show all received direct messages for you.")
        print("connections                  - Show your followers and who you are following.")
        print("verbose                      - Toggle detailed message logging ON/OFF.")
        print("help                         - Show this help message.")
        print("quit                         - Shut down the client.")
        print("--------------------------")

    def _send_profile_command(self, args, destination_addr=BROADCAST_ADDR):
        if not args:
            print("Usage: profile <status>")
            return
        payload = {
            'TYPE': 'PROFILE',
            'USER_ID': self.user_id,
            'DISPLAY_NAME': self.username,
            'STATUS': args
        }
        self._send_message(payload, destination_addr)
        if destination_addr == BROADCAST_ADDR:
            print("Profile broadcasted.")

    def _send_post_command(self, args):
        if not args:
            print("Usage: post <content>")
            return
        # This is broadcast, but only followers should accept it.
        payload = {
            'TYPE': 'POST',
            'USER_ID': self.user_id,
            'CONTENT': args,
            'MESSAGE_ID': uuid.uuid4().hex[:16],
            'TIMESTAMP': int(time.time()),
            'TTL': 3600,
            # Placeholder token for now
            'TOKEN': f"{self.user_id}|{int(time.time()) + 3600}|broadcast"
        }
        self._send_message(payload, BROADCAST_ADDR)
        print("Post broadcasted.")

    def _send_dm_command(self, args):
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: dm <user_id> <message>")
            return
        recipient_id, message = parts
        
        recipient_ip = self._get_ip_for_user(recipient_id)
        if not recipient_ip:
            print(f"Error: Could not determine IP for '{recipient_id}'. Make sure they are a known peer.")
            return

        payload = {
            'TYPE': 'DM',
            'FROM': self.user_id,
            'TO': recipient_id,
            'CONTENT': message,
            'MESSAGE_ID': uuid.uuid4().hex[:16],
            'TIMESTAMP': int(time.time()),
            # Placeholder token for now
            'TOKEN': f"{self.user_id}|{int(time.time()) + 3600}|chat"
        }
        self._send_message(payload, (recipient_ip, PORT))
        print(f"DM sent to {recipient_id}.")
        
    def _send_follow_command(self, args):
        recipient_id = args.strip()
        if not recipient_id:
            print("Usage: follow <user_id>")
            return
            
        if recipient_id == self.user_id:
            print("You cannot follow yourself.")
            return

        recipient_ip = self._get_ip_for_user(recipient_id)
        if not recipient_ip:
            print(f"Error: Could not determine IP for '{recipient_id}'. Make sure they are a known peer.")
            return
            
        payload = {
            'TYPE': 'FOLLOW',
            'FROM': self.user_id,
            'TO': recipient_id,
            'MESSAGE_ID': uuid.uuid4().hex[:16],
            'TIMESTAMP': int(time.time()),
            # Placeholder token for now
            'TOKEN': f"{self.user_id}|{int(time.time()) + 3600}|follow"
        }
        self._send_message(payload, (recipient_ip, PORT))
        self.following.add(recipient_id)
        print(f"You are now following {recipient_id}.")

    def _send_unfollow_command(self, args):
        recipient_id = args.strip()
        if not recipient_id:
            print("Usage: unfollow <user_id>")
            return

        recipient_ip = self._get_ip_for_user(recipient_id)
        if not recipient_ip:
            print(f"Error: Could not determine IP for '{recipient_id}'. Make sure they are a known peer.")
            return
            
        payload = {
            'TYPE': 'UNFOLLOW',
            'FROM': self.user_id,
            'TO': recipient_id,
            'MESSAGE_ID': uuid.uuid4().hex[:16],
            'TIMESTAMP': int(time.time()),
            # Placeholder token for now
            'TOKEN': f"{self.user_id}|{int(time.time()) + 3600}|follow"
        }
        self._send_message(payload, (recipient_ip, PORT))
        self.following.discard(recipient_id)
        print(f"You have unfollowed {recipient_id}.")

    def _get_ip_for_user(self, user_id):
        """Helper to find an IP for a given user_id from known peers or the ID itself."""
        if '@' in user_id:
            return user_id.split('@')[1]
        # Fallback to check known_peers if a plain username is given
        for peer_id, data in self.known_peers.items():
            if data.get('DISPLAY_NAME') == user_id:
                if '@' in peer_id:
                    return peer_id.split('@')[1]
        return None

    def _print_peers(self):
        print("\n--- Known Peers ---")
        if not self.known_peers:
            print("No peers discovered yet. Wait for a PROFILE or PING message.")
        else:
            for user_id, data in self.known_peers.items():
                name = data.get('DISPLAY_NAME', 'N/A')
                status = data.get('STATUS', 'N/A')
                print(f"- {name} ({user_id}): {status}")
        print("-------------------")

    def _print_posts(self):
        print("\n--- Public Posts (from users you follow) ---")
        if not self.posts:
            print("No posts received yet.")
        else:
            for i, post in enumerate(self.posts):
                sender = post.get('USER_ID', 'Unknown')
                content = post.get('CONTENT', '')
                print(f"{i+1}. From {sender}: {content}")
        print("--------------------------------------------")

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

    def _print_connections(self):
        print("\n--- Your Connections ---")
        print("Following:")
        if not self.following:
            print("  (You are not following anyone)")
        else:
            for user in self.following:
                print(f"  - {user}")
        
        print("\nFollowers:")
        if not self.followers:
            print("  (You have no followers)")
        else:
            for user in self.followers:
                print(f"  - {user}")
        print("------------------------")


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            peer_username = sys.argv[1]
        else:
            peer_username = input("Enter your username: ").strip()

        peer = LsnpPeer(username=peer_username)
        peer.start()

    except ValueError as e:
        print(f"[FATAL] {e}")
    except KeyboardInterrupt:
        print("\nUser interrupted. Shutting down.")
    finally:
        print("\nApplication has been terminated.")