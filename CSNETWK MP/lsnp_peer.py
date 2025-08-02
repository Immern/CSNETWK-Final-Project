import socket
import threading
import time
import sys
import uuid

# LSNP Constants
PORT = 50999
BROADCAST_ADDR = '<broadcast>'
PRESENCE_INTERVAL = 30 # Seconds (changed from 300 for easier testing)

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

        # Data stores for received messages and state
        self.known_peers = {} # Maps user_id to peer data
        self.posts = []
        self.dms = []
        self.followers = set()
        self.following = set()
        self.groups = {} # Maps group_id to group data
        self.games = {} # Maps game_id to game state

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
        """Finds the local IP address of the machine."""
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
        """Starts the peer's operation by launching listener and command threads."""
        print("\nStarting LSNP Peer... Type 'help' for a list of commands.")
        
        # Thread for listening to incoming messages
        listener_thread = threading.Thread(target=self._listen, daemon=True)
        listener_thread.start()

        # Thread for broadcasting presence periodically
        presence_thread = threading.Thread(target=self._periodic_presence, daemon=True)
        presence_thread.start()

        # The main thread will handle the command loop
        self._command_loop()

    def stop(self):
        """Stops the peer and cleans up resources."""
        print("\nShutting down LSNP Peer...")
        self.running = False
        self.socket.close()
        print("Shutdown complete.")

    def _listen(self):
        """Continuously listens for incoming UDP messages."""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(8192)
                if data:
                    self._handle_message(data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[ERROR] An error occurred in the listener: {e}")
                break

    def _periodic_presence(self):
        """Periodically broadcasts a PROFILE message to the network to ensure robust discovery."""
        # Wait a moment after startup before the first broadcast
        time.sleep(2)
        while self.running:
            if self.verbose:
                print("\n[Auto] Sending periodic profile broadcast to maintain presence.")
            
            # Send a profile message to announce presence and share details
            self._send_profile_command(args="Online", is_auto=True)
            
            time.sleep(PRESENCE_INTERVAL)


    def _handle_message(self, data, addr):
        """Processes a received message."""
        try:
            message_str = data.decode('utf-8')
            parsed_message = self._parse_message(message_str)

            # Get the sender's ID from the message payload
            sender_id = parsed_message.get('USER_ID') or parsed_message.get('FROM')

            # **FIX**: Ignore messages broadcast by the peer itself
            if sender_id == self.user_id:
                return

            if self.verbose:
                print("\n--- RECV ---")
                print(f"From: {addr}")
                print(f"Raw: {message_str.strip()}")
                print(f"Parsed: {parsed_message}")
                print("------------")

            msg_type = parsed_message.get('TYPE')

            if msg_type == 'PROFILE':
                user_id = parsed_message.get('USER_ID')
                if user_id and user_id not in self.known_peers:
                    print(f"\n[Discovery] New peer discovered: {user_id}")
                    print(f"({self.username}) > ", end='', flush=True)
                    self.known_peers[user_id] = parsed_message
                elif user_id: # Update existing peer data
                    self.known_peers[user_id] = parsed_message
            
            elif msg_type == 'POST':
                # Per RFC, only show posts from users you follow
                if sender_id in self.following:
                    self.posts.append(parsed_message)
                    print(f"\n[New Post] From {sender_id}: {parsed_message.get('CONTENT')}")
                    print(f"({self.username}) > ", end='', flush=True)
                elif self.verbose:
                    print(f"\n[Ignored Post] From non-followed user: {sender_id}")

            elif msg_type == 'DM':
                if parsed_message.get('TO') == self.user_id:
                    self.dms.append(parsed_message)
                    print(f"\n[DM] From {sender_id}: {parsed_message.get('CONTENT')}")
                    print(f"({self.username}) > ", end='', flush=True)

            elif msg_type == 'FOLLOW':
                if parsed_message.get('TO') == self.user_id:
                    self.followers.add(sender_id)
                    print(f"\n[Notification] User {sender_id} has followed you.")
                    print(f"({self.username}) > ", end='', flush=True)
            
            elif msg_type == 'UNFOLLOW':
                 if parsed_message.get('TO') == self.user_id:
                    self.followers.discard(sender_id)
                    print(f"\n[Notification] User {sender_id} has unfollowed you.")
                    print(f"({self.username}) > ", end='', flush=True)
            
            # Other message types from Milestone 1 test suite
            elif msg_type == 'LIKE':
                if parsed_message.get('TO') == self.user_id:
                    print(f"\n[Notification] {sender_id} liked your post.")
                    print(f"({self.username}) > ", end='', flush=True)
            elif msg_type == 'GROUP_CREATE':
                if self.user_id in parsed_message.get('MEMBERS', ''):
                    group_id = parsed_message.get('GROUP_ID')
                    self.groups[group_id] = parsed_message
                    print(f"\n[Notification] You've been added to group: {parsed_message.get('GROUP_NAME')}")
                    print(f"({self.username}) > ", end='', flush=True)
            elif msg_type == 'GROUP_MESSAGE':
                 if parsed_message.get('GROUP_ID') in self.groups:
                     print(f"\n[Group Message] {sender_id}: {parsed_message.get('CONTENT')}")
                     print(f"({self.username}) > ", end='', flush=True)
            elif msg_type == 'TICTACTOE_INVITE':
                if parsed_message.get('TO') == self.user_id:
                    print(f"\n[Game] {sender_id} is inviting you to play Tic Tac Toe.")
                    print(f"({self.username}) > ", end='', flush=True)

        except (UnicodeDecodeError, ValueError) as e:
            print(f"\n[ERROR] Could not process message from {addr}: {e}")

    def _parse_message(self, message_str):
        """Parses a raw LSNP message string into a dictionary."""
        if not message_str.strip().endswith('\n'):
            message_str += '\n\n'
        
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
                if key in ['AVATAR_DATA', 'DATA']:
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
        """Formats a dictionary payload into a valid LSNP message string."""
        message_parts = []
        for key, value in payload.items():
            message_parts.append(f"{key}: {value}")
        return '\n'.join(message_parts) + '\n\n'

    def _send_message(self, payload, destination_addr):
        """Formats and sends a message to a given destination."""
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

    def _get_recipient_ip(self, user_id):
        """Helper to find an IP for a given user_id from known peers."""
        if '@' in user_id:
            try:
                return user_id.split('@')[1]
            except IndexError:
                return None
        return None

    def _command_loop(self):
        """Handles user input from the command line."""
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
                elif command == 'follow':
                    self._send_follow_command(args, 'FOLLOW')
                elif command == 'unfollow':
                    self._send_follow_command(args, 'UNFOLLOW')
                elif command == 'followers':
                    self._print_followers()
                elif command == 'following':
                    self._print_following()
                elif command == 'like':
                    self._send_like_command(args)
                elif command == 'group':
                    self._handle_group_command(args)
                elif command == 'game':
                    self._handle_game_command(args)
                else:
                    print(f"Unknown command: '{command}'. Type 'help' for a list of commands.")
            except (KeyboardInterrupt, EOFError):
                self.running = False
            except Exception as e:
                print(f"[ERROR] An error occurred in the command loop: {e}")

    def _print_help(self):
        print("\n--- LSNP Client Commands ---")
        print("profile <status>             - Broadcast your profile with a new status.")
        print("post <content>               - Broadcast a public post to your followers.")
        print("dm <user_id> <message>       - Send a direct message to a user.")
        print("follow <user_id>             - Follow a user to subscribe to their posts.")
        print("unfollow <user_id>           - Unfollow a user.")
        print("followers                    - Show a list of your followers.")
        print("following                    - Show a list of users you are following.")
        print("like <user_id> <post_ts>     - Like a user's post, identified by its timestamp.")
        print("group create <id> <name>     - Create a new group.")
        print("group msg <id> <message>     - Send a message to a group.")
        print("game invite <user_id>        - Invite a user to play Tic Tac Toe.")
        print("peers                        - List all known peers on the network.")
        print("posts                        - Show all received public posts from users you follow.")
        print("dms                          - Show all received direct messages for you.")
        print("verbose                      - Toggle detailed message logging ON/OFF.")
        print("help                         - Show this help message.")
        print("quit                         - Shut down the client.")
        print("--------------------------")

    def _send_profile_command(self, args, is_auto=False):
        """Sends a profile message. Can be called automatically or by user."""
        status = args
        if not status:
            print("Usage: profile <status>")
            return
        
        payload = {
            'TYPE': 'PROFILE',
            'USER_ID': self.user_id,
            'DISPLAY_NAME': self.username,
            'STATUS': status
        }
        self._send_message(payload, BROADCAST_ADDR)
        
        # Only print confirmation for user-initiated broadcasts
        if not is_auto:
            print("Profile broadcasted.")

    def _send_post_command(self, args):
        if not args:
            print("Usage: post <content>")
            return
        ts = int(time.time())
        payload = {
            'TYPE': 'POST',
            'USER_ID': self.user_id,
            'CONTENT': args,
            'MESSAGE_ID': uuid.uuid4().hex[:8],
            'TIMESTAMP': ts,
            'TTL': 3600,
            'TOKEN': f"{self.user_id} {ts+3600}|broadcast"
        }
        self._send_message(payload, BROADCAST_ADDR)
        print(f"Post broadcasted to followers with timestamp {ts}.")

    def _send_dm_command(self, args):
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: dm <user_id> <message>")
            return
        recipient_id, message = parts
        
        recipient_ip = self._get_recipient_ip(recipient_id)
        if not recipient_ip:
            print(f"Error: Could not determine IP for '{recipient_id}'. Make sure they have sent a profile message.")
            return
        
        ts = int(time.time())
        payload = {
            'TYPE': 'DM',
            'FROM': self.user_id,
            'TO': recipient_id,
            'CONTENT': message,
            'MESSAGE_ID': uuid.uuid4().hex[:8],
            'TIMESTAMP': ts,
            'TOKEN': f"{self.user_id} {ts+3600}|chat"
        }
        self._send_message(payload, (recipient_ip, PORT))
        print(f"DM sent to {recipient_id}.")

    def _send_follow_command(self, args, action_type):
        if not args:
            print(f"Usage: {action_type.lower()} <user_id>")
            return
        recipient_id = args

        if recipient_id == self.user_id:
            print("You cannot follow yourself.")
            return

        recipient_ip = self._get_recipient_ip(recipient_id)
        if not recipient_ip:
            print(f"Error: Could not determine IP for '{recipient_id}'.")
            return

        ts = int(time.time())
        payload = {
            'TYPE': action_type,
            'MESSAGE_ID': uuid.uuid4().hex[:8],
            'FROM': self.user_id,
            'TO': recipient_id,
            'TIMESTAMP': ts,
            'TOKEN': f"{self.user_id} {ts+3600}|follow"
        }
        self._send_message(payload, (recipient_ip, PORT))
        if action_type == 'FOLLOW':
            self.following.add(recipient_id)
            print(f"You are now following {recipient_id}.")
        else:
            self.following.discard(recipient_id)
            print(f"You have unfollowed {recipient_id}.")

    def _send_like_command(self, args):
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: like <user_id> <post_timestamp>")
            return
        recipient_id, post_ts = parts
        
        recipient_ip = self._get_recipient_ip(recipient_id)
        if not recipient_ip:
            print(f"Error: Could not determine IP for '{recipient_id}'.")
            return
        
        ts = int(time.time())
        payload = {
            'TYPE': 'LIKE',
            'FROM': self.user_id,
            'TO': recipient_id,
            'POST_TIMESTAMP': post_ts,
            'ACTION': 'LIKE',
            'TIMESTAMP': ts,
            'TOKEN': f"{self.user_id} {ts+3600}|broadcast"
        }
        self._send_message(payload, (recipient_ip, PORT))
        print(f"Like sent for post {post_ts} to {recipient_id}.")

    def _handle_group_command(self, args):
        parts = args.split(maxsplit=2)
        sub_command = parts[0].lower() if parts else ""

        if sub_command == "create":
            if len(parts) < 3:
                print("Usage: group create <group_id> <group_name>")
                return
            group_id, group_name = parts[1], parts[2]
            ts = int(time.time())
            payload = {
                'TYPE': 'GROUP_CREATE',
                'FROM': self.user_id,
                'GROUP_ID': group_id,
                'GROUP_NAME': group_name,
                'MEMBERS': self.user_id,
                'TIMESTAMP': ts,
                'TOKEN': f"{self.user_id} {ts+3600}|group"
            }
            self.groups[group_id] = payload
            self._send_message(payload, BROADCAST_ADDR)
            print(f"Group '{group_name}' created with ID '{group_id}'.")
        
        elif sub_command == "msg":
            if len(parts) < 3:
                print("Usage: group msg <group_id> <message>")
                return
            group_id, content = parts[1], parts[2]
            if group_id not in self.groups:
                print("Error: You are not a member of that group.")
                return
            ts = int(time.time())
            payload = {
                'TYPE': 'GROUP_MESSAGE',
                'FROM': self.user_id,
                'GROUP_ID': group_id,
                'CONTENT': content,
                'TIMESTAMP': ts,
                'TOKEN': f"{self.user_id} {ts+3600}|group"
            }
            self._send_message(payload, BROADCAST_ADDR)
            print(f"Message sent to group '{group_id}'.")
        else:
            print("Unknown group command. Use 'group create' or 'group msg'.")

    def _handle_game_command(self, args):
        parts = args.split(maxsplit=1)
        sub_command = parts[0].lower() if parts else ""

        if sub_command == "invite":
            if len(parts) < 2:
                print("Usage: game invite <user_id>")
                return
            recipient_id = parts[1]
            recipient_ip = self._get_recipient_ip(recipient_id)
            if not recipient_ip:
                print(f"Error: Could not determine IP for '{recipient_id}'.")
                return
            
            ts = int(time.time())
            game_id = f"g{uuid.uuid4().int & (1<<8)-1}"
            payload = {
                'TYPE': 'TICTACTOE_INVITE',
                'FROM': self.user_id,
                'TO': recipient_id,
                'GAMEID': game_id,
                'MESSAGE_ID': uuid.uuid4().hex[:8],
                'SYMBOL': 'X',
                'TIMESTAMP': ts,
                'TOKEN': f"{self.user_id} {ts+3600}|game"
            }
            self._send_message(payload, (recipient_ip, PORT))
            print(f"Tic Tac Toe invitation sent to {recipient_id}.")
        else:
            print("Unknown game command. Use 'game invite'.")

    def _print_peers(self):
        print("\n--- Known Peers ---")
        if not self.known_peers:
            print("No peers discovered yet. Wait for a PROFILE broadcast.")
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
                ts = post.get('TIMESTAMP', 'N/A')
                print(f"{i+1}. (TS: {ts}) From {sender}: {content}")
        print("---------------------------------------------")

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

    def _print_followers(self):
        print("\n--- Your Followers ---")
        if not self.followers:
            print("You have no followers yet.")
        else:
            for follower_id in self.followers:
                print(f"- {follower_id}")
        print("----------------------")

    def _print_following(self):
        print("\n--- Users You Follow ---")
        if not self.following:
            print("You are not following anyone yet.")
        else:
            for following_id in self.following:
                print(f"- {following_id}")
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