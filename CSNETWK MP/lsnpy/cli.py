import sys
import time
import uuid
import threading
from lsnpy.core import LsnpPeer, BROADCAST_ADDR, PORT

class LsnpCli:
    """
    Manages the command-line interface and user input for the LSNP peer.
    """

    def __init__(self, peer):
        self.peer = peer
    
    def start_command_loop(self):
        """Starts the main command loop for user input."""
        print("\nStarting LSNP Client... Type 'help' for a list of commands.")
        try:
            self._command_loop()
        except (KeyboardInterrupt, EOFError):
            print("\nUser interrupted. Shutting down.")
        finally:
            self.peer.stop()

    def _command_loop(self):
        """Handles user input from the command line."""
        while self.peer.running:
            try:
                cmd_input = input(f"\n({self.peer.username}) > ").strip()
                if not cmd_input:
                    continue

                parts = cmd_input.split(maxsplit=1)
                command = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                command_methods = {
                    'quit': self._quit_command,
                    'help': self._print_help,
                    'verbose': self._toggle_verbose,
                    'profile': self._send_profile_command,
                    'post': self._send_post_command,
                    'dm': self._send_dm_command,
                    'peers': self._print_peers,
                    'posts': self._print_posts,
                    'dms': self._print_dms,
                    'follow': self._send_follow_command,
                    'unfollow': self._send_unfollow_command,
                    'followers': self._print_followers,
                    'following': self._print_following,
                    'like': self._send_like_command,
                    'group': self._handle_group_command,
                    'game': self._handle_game_command,
                }
                
                method = command_methods.get(command)
                if method:
                    method(args)
                else:
                    print(f"Unknown command: '{command}'. Type 'help' for a list of commands.")
            except Exception as e:
                print(f"[ERROR] An error occurred in the command loop: {e}")

    def _quit_command(self, args):
        self.peer.running = False
        
    def _toggle_verbose(self, args):
        self.peer.verbose = not self.peer.verbose
        print(f"Verbose mode is now {'ON' if self.peer.verbose else 'OFF'}.")

    def _send_profile_command(self, args):
        status = args
        if not status:
            print("Usage: profile <status>")
            return
        
        payload = {
            'TYPE': 'PROFILE',
            'USER_ID': self.peer.user_id,
            'DISPLAY_NAME': self.peer.username,
            'STATUS': status
        }
        self.peer._send_message(payload, BROADCAST_ADDR)
        print("Profile broadcasted.")

    # All other command-related methods and print functions go here.
    # e.g., _send_post_command, _send_dm_command, _print_peers, etc.
    # They will all take `self` and `args` and access `self.peer` for state.
    
    def _print_help(self, args):
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
        
    def _print_peers(self, args):
        print("\n--- Known Peers ---")
        if not self.peer.known_peers:
            print("No peers discovered yet. Wait for a PROFILE broadcast.")
        else:
            for user_id, data in self.peer.known_peers.items():
                name = data.get('DISPLAY_NAME', 'N/A')
                status = data.get('STATUS', 'N/A')
                print(f"- {name} ({user_id}): {status}")
        print("-------------------")
        
    def _send_post_command(self, args):
        if not args:
            print("Usage: post <content>")
            return
        ts = int(time.time())
        payload = {
            'TYPE': 'POST',
            'USER_ID': self.peer.user_id,
            'CONTENT': args,
            'TTL': 3600,
            'MESSAGE_ID': uuid.uuid4().hex[:8],
            'TOKEN': f"{self.peer.user_id}|{ts+3600}|broadcast"
        }
        self.peer._send_message(payload, BROADCAST_ADDR)
        print(f"Post broadcasted to followers with timestamp {ts}.")

    def _send_dm_command(self, args):
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: dm <user_id> <message>")
            return
        recipient_id, message = parts
        
        recipient_ip = self.peer.get_recipient_ip(recipient_id)
        if not recipient_ip:
            print(f"Error: Could not determine IP for '{recipient_id}'. Make sure they have sent a profile message.")
            return
        
        ts = int(time.time())
        payload = {
            'TYPE': 'DM',
            'FROM': self.peer.user_id,
            'TO': recipient_id,
            'CONTENT': message,
            'TIMESTAMP': ts,
            'MESSAGE_ID': uuid.uuid4().hex[:8],
            'TOKEN': f"{self.peer.user_id}|{ts+3600}|chat"
        }
        self.peer._send_message(payload, (recipient_ip, PORT))
        print(f"DM sent to {recipient_id}.")
        
    def _send_follow_command(self, args, action_type='FOLLOW'):
        if not args:
            print(f"Usage: {action_type.lower()} <user_id>")
            return
        recipient_id = args

        if recipient_id == self.peer.user_id:
            print("You cannot follow yourself.")
            return

        recipient_ip = self.peer.get_recipient_ip(recipient_id)
        if not recipient_ip:
            print(f"Error: Could not determine IP for '{recipient_id}'.")
            return

        ts = int(time.time())
        payload = {
            'TYPE': action_type,
            'MESSAGE_ID': uuid.uuid4().hex[:8],
            'FROM': self.peer.user_id,
            'TO': recipient_id,
            'TIMESTAMP': ts,
            'TOKEN': f"{self.peer.user_id}|{ts+3600}|follow"
        }
        self.peer._send_message(payload, (recipient_ip, PORT))
        if action_type == 'FOLLOW':
            self.peer.following.add(recipient_id)
            print(f"You are now following {recipient_id}.")
        else:
            self.peer.following.discard(recipient_id)
            print(f"You have unfollowed {recipient_id}.")

    def _send_unfollow_command(self, args):
        self._send_follow_command(args, action_type='UNFOLLOW')

    def _send_like_command(self, args):
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print("Usage: like <user_id> <post_timestamp>")
            return
        recipient_id, post_ts = parts
        
        recipient_ip = self.peer.get_recipient_ip(recipient_id)
        if not recipient_ip:
            print(f"Error: Could not determine IP for '{recipient_id}'.")
            return
        
        ts = int(time.time())
        payload = {
            'TYPE': 'LIKE',
            'FROM': self.peer.user_id,
            'TO': recipient_id,
            'POST_TIMESTAMP': post_ts,
            'ACTION': 'LIKE',
            'TIMESTAMP': ts,
            'TOKEN': f"{self.peer.user_id} {ts+3600}|broadcast"
        }
        self.peer._send_message(payload, (recipient_ip, PORT))
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
                'FROM': self.peer.user_id,
                'GROUP_ID': group_id,
                'GROUP_NAME': group_name,
                'MEMBERS': self.peer.user_id,
                'TIMESTAMP': ts,
                'TOKEN': f"{self.peer.user_id}|{ts+3600}|group"
            }
            self.peer.groups[group_id] = payload
            self.peer._send_message(payload, BROADCAST_ADDR)
            print(f"Group '{group_name}' created with ID '{group_id}'.")
        
        elif sub_command == "msg":
            if len(parts) < 3:
                print("Usage: group msg <group_id> <message>")
                return
            group_id, content = parts[1], parts[2]
            if group_id not in self.peer.groups:
                print("Error: You are not a member of that group.")
                return
            ts = int(time.time())
            payload = {
                'TYPE': 'GROUP_MESSAGE',
                'FROM': self.peer.user_id,
                'GROUP_ID': group_id,
                'CONTENT': content,
                'TIMESTAMP': ts,
                'TOKEN': f"{self.peer.user_id} {ts+3600}|group"
            }
            self.peer._send_message(payload, BROADCAST_ADDR)
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
            recipient_ip = self.peer.get_recipient_ip(recipient_id)
            if not recipient_ip:
                print(f"Error: Could not determine IP for '{recipient_id}'.")
                return
            
            ts = int(time.time())
            game_id = f"g{uuid.uuid4().int & (1<<8)-1}"
            payload = {
                'TYPE': 'TICTACTOE_INVITE',
                'FROM': self.peer.user_id,
                'TO': recipient_id,
                'GAMEID': game_id,
                'MESSAGE_ID': uuid.uuid4().hex[:8],
                'SYMBOL': 'X',
                'TIMESTAMP': ts,
                'TOKEN': f"{self.peer.user_id} {ts+3600}|game"
            }
            self.peer._send_message(payload, (recipient_ip, PORT))
            print(f"Tic Tac Toe invitation sent to {recipient_id}.")
        else:
            print("Unknown game command. Use 'game invite'.")

    def _print_posts(self, args):
        print("\n--- Public Posts (from users you follow) ---")
        if not self.peer.posts:
            print("No posts received yet.")
        else:
            for i, post in enumerate(self.peer.posts):
                sender = post.get('USER_ID', 'Unknown')
                content = post.get('CONTENT', '')
                ts = post.get('TIMESTAMP', 'N/A')
                print(f"{i+1}. (TS: {ts}) From {sender}: {content}")
        print("---------------------------------------------")

    def _print_dms(self, args):
        print("\n--- Direct Messages for You ---")
        if not self.peer.dms:
            print("No DMs received yet.")
        else:
            for i, dm in enumerate(self.peer.dms):
                sender = dm.get('FROM', 'Unknown')
                content = dm.get('CONTENT', '')
                print(f"{i+1}. From {sender}: {content}")
        print("-------------------------------")

    def _print_followers(self, args):
        print("\n--- Your Followers ---")
        if not self.peer.followers:
            print("You have no followers yet.")
        else:
            for follower_id in self.peer.followers:
                print(f"- {follower_id}")
        print("----------------------")

    def _print_following(self, args):
        print("\n--- Users You Follow ---")
        if not self.peer.following:
            print("You are not following anyone yet.")
        else:
            for following_id in self.peer.following:
                print(f"- {following_id}")
        print("------------------------")