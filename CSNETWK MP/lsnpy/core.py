import socket
import threading
import time
import uuid

# LSNP Constants
PORT = 50999
BROADCAST_ADDR = '<broadcast>'
PRESENCE_INTERVAL = 30 # Seconds

class LsnpPeer:
    """
    Implements the core functionality for a peer in the Local Social Networking Protocol.
    This class handles network communication and maintains the peer's state.
    """

    def __init__(self, username, message_handler, bind_ip=''): # Corrected: Added 'bind_ip' parameter
        """
        Initializes the LSNP peer.
        Args:
            username (str): The display name for this user.
            message_handler (LsnpMessageHandler): An object to handle incoming messages.
            bind_ip (str): The IP address to bind the socket to.
        """
        if not username:
            raise ValueError("Username cannot be empty.")

        self.username = username
        self.verbose = False
        self.running = True
        self.message_handler = message_handler

        # Data stores for received messages and state
        self.known_peers = {} # Maps user_id to peer data
        self.posts = []
        self.dms = []
        self.followers = set()
        self.following = set()
        self.groups = {} # Maps group_id to group data
        self.pending_game_invites = {}
        self.active_games = {}
        
        # Set up the UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            self.socket.bind((bind_ip, PORT)) # Use the bind_ip here
        except Exception as e:
            raise OSError(f"Could not bind to port {PORT}. Is another instance already running? Error: {e}")
        self.socket.settimeout(1.0)

        # Get the IP address used for this peer
        self.ip = self.socket.getsockname()[0]
        if self.ip == '0.0.0.0' or self.ip == '':
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                self.ip = s.getsockname()[0]
            except Exception:
                self.ip = '127.0.0.1' # Fallback to loopback
            finally:
                s.close()
            
        self.user_id = f"{self.username}@{self.ip}"

        print(f"LSNP Peer '{self.username}' initialized.")
        print(f"Your USER_ID is: {self.user_id}")
        print(f"Listening on port {PORT}...")

    def _get_local_ip(self):
        """Finds the local IP address of the machine."""
        # This part remains the same
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def start_network_threads(self):
        """Starts the peer's network listening and presence broadcasting threads."""
        listener_thread = threading.Thread(target=self._listen, daemon=True)
        listener_thread.start()

        presence_thread = threading.Thread(target=self._periodic_presence, daemon=True)
        presence_thread.start()
        
    def stop(self):
        """Stops the peer and cleans up resources."""
        print("\nShutting down LSNP Peer...")
        self.running = False
        self.socket.close()
        print("Shutdown complete.")

    def _listen(self):
        """Continuously listens for incoming UDP messages."""
        print(f"[{self.username}] Listener thread started. Waiting for messages...")
        while self.running:
            try:
                data, addr = self.socket.recvfrom(8192)
                if data:
                    print(f"[{self.username}] Data received from {addr}!")
                    print(f"[{self.username}] Raw data: {data.decode('utf-8')}")
                    # Delegate message handling to the message_handler object
                    self.message_handler.handle(self, data, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[{self.username}] An error occurred in the listener: {e}")
                break
        print(f"[{self.username}] Listener thread stopped.")

    def _periodic_presence(self):
        """Periodically broadcasts a PROFILE message to the network."""
        time.sleep(2)
        while self.running:
            if self.verbose:
                print("\n[Auto] Sending periodic profile broadcast to maintain presence.")
            
            # Send a profile message
            payload = {
                'TYPE': 'PROFILE',
                'USER_ID': self.user_id,
                'DISPLAY_NAME': self.username,
                'STATUS': "Online"
            }
            self._send_message(payload, BROADCAST_ADDR)
            
            time.sleep(PRESENCE_INTERVAL)

    def _parse_message(self, message_str):
        # This part of the code remains the same.
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
                    print(f"\n--- SENT (Broadcast) ---\n{message_str.strip()}\n------------------------")
            else:
                self.socket.sendto(message_bytes, destination_addr)
                if self.verbose:
                    print(f"\n--- SENT (Unicast to {destination_addr}) ---\n{message_str.strip()}\n---------------------------------------")
        except Exception as e:
            print(f"\n[ERROR] Could not send message: {e}")

    def get_recipient_ip(self, user_id):
        """Helper to find an IP for a given user_id from known peers."""
        if '@' in user_id:
            try:
                return user_id.split('@')[1]
            except IndexError:
                return None
        return None
