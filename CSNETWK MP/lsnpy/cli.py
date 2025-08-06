import sys
import time
import uuid
import threading
from lsnpy.core import LsnpPeer, BROADCAST_ADDR, PORT
from lsnpy.handlers import TicTacToe

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
                    'tictactoe_invite': self._handle_tictactoe_invite_command,
                    'tictactoe_accept': self._handle_tictactoe_accept_command, # New command
                    'tictactoe_move': self._handle_tictactoe_move_command,
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
    
    def _print_help(self, args):
        """Prints the updated, aligned help menu."""
        print("\n--- LSNP Client Commands ---")
        commands = [
            ("profile", "<status>", "Broadcast your profile with a new status."),
            ("post", "<content>", "Broadcast a public post to your followers."),
            ("dm", "<user_id> <message>", "Send a direct message to a user."),
            ("follow", "<user_id>", "Follow a user to subscribe to their posts."),
            ("unfollow", "<user_id>", "Unfollow a user."),
            ("like", "<user_id> <post_ts>", "Like a user's post."),
            ("group create", "<id> <name>", "Create a new group."),
            ("group msg", "<id> <message>", "Send a message to a group."),
            ("tictactoe_invite", "<user_id>", "Invite a user to play Tic Tac Toe."),
            ("tictactoe_accept", "<game_id>", "Accept a Tic Tac Toe game invitation."),
            ("tictactoe_move", "<game_id> <pos>", "Make a move in an active game (pos 0-8)."),
            ("followers", "", "Show a list of your followers."),
            ("following", "", "Show a list of users you are following."),
            ("peers", "", "List all known peers on the network."),
            ("posts", "", "Show all received public posts."),
            ("dms", "", "Show all received direct messages."),
            ("verbose", "", "Toggle detailed message logging ON/OFF."),
            ("help", "", "Show this help message."),
            ("quit", "", "Shut down the client."),
        ]
        cmd_col_width = 20
        args_col_width = 25
        for cmd, cmd_args, desc in commands:
            padded_cmd = f"{cmd:<{cmd_col_width}}"
            padded_args = f"{cmd_args:<{args_col_width}}"
            print(f"{padded_cmd}{padded_args}- {desc}")
        print("---------------------------------")
        
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
            print(f"Error: Could not determine IP for '{recipient_id}'.")
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
            'TOKEN': f"{self.peer.user_id}|{ts+3600}|broadcast"
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

    def _handle_tictactoe_invite_command(self, args):
        if not args:
            print("Usage: tictactoe_invite <user_id>")
            return
        recipient_id = args
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
            'TOKEN': f"{self.peer.user_id}|{ts+3600}|game"
        }
        self.peer.pending_game_invites[game_id] = payload
        self.peer._send_message(payload, (recipient_ip, PORT))
        print(f"Tic Tac Toe invitation sent to {recipient_id} (Game ID: {game_id}).")
        
    def _handle_tictactoe_accept_command(self, args):
        """Accepts a game invite and starts the game."""
        game_id = args
        if not game_id:
            print("Usage: tictactoe_accept <game_id>")
            return

        invite = self.peer.pending_game_invites.get(game_id)
        if not invite:
            print(f"Error: No pending invite found for game ID '{game_id}'.")
            return

        inviter_id = invite.get('FROM')
        inviter_ip = self.peer.get_recipient_ip(inviter_id)
        if not inviter_ip:
            print(f"Error: Could not find IP for inviter '{inviter_id}'.")
            return

        # Create the game locally (acceptor is 'O')
        self.peer.active_games[game_id] = TicTacToe(inviter_id, self.peer.user_id)
        game = self.peer.active_games[game_id]
        
        # Send the acceptance message
        payload = {
            'TYPE': 'TICTACTOE_ACCEPT',
            'FROM': self.peer.user_id,
            'TO': inviter_id,
            'GAMEID': game_id,
            'TIMESTAMP': int(time.time()),
            'TOKEN': f"{self.peer.user_id}|{int(time.time())+3600}|game"
        }
        self.peer._send_message(payload, (inviter_ip, PORT))
        
        # Clean up the pending invite
        del self.peer.pending_game_invites[game_id]
        
        print(f"You have accepted the game invite from {inviter_id}. The game has started!")
        game.display_board()
        print(f"Waiting for {inviter_id} to make the first move.")

    def _handle_tictactoe_move_command(self, args):
        """Sends a move for an active game."""
        parts = args.split()
        if len(parts) != 2:
            print("Usage: tictactoe_move <game_id> <position>")
            return

        game_id, position_str = parts
        game = self.peer.active_games.get(game_id)
        if not game:
            print(f"Error: No active game found with ID '{game_id}'.")
            return

        try:
            position = int(position_str)
            if not 0 <= position <= 8:
                raise ValueError
        except ValueError:
            print(f"Invalid position: {position_str}. Use a number between 0 and 8.")
            return
            
        # Determine opponent and their IP
        opponent_id = game.players['O' if game.players['X'] == self.peer.user_id else 'X']
        opponent_ip = self.peer.get_recipient_ip(opponent_id)

        # Validate the move
        if game.players[game.current_player_symbol] != self.peer.user_id:
            print("Error: It is not your turn.")
            return
            
        row, col = position // 3, position % 3
        success, message = game.make_move(self.peer.user_id, row, col)
        if not success:
            print(f"Error: {message}")
            return
        
        # Send the move message
        payload = {
            'TYPE': 'TICTACTOE_MOVE', 'FROM': self.peer.user_id, 'TO': opponent_id,
            'GAMEID': game_id, 'POSITION': position, 'TIMESTAMP': int(time.time()),
            'MESSAGE_ID': uuid.uuid4().hex[:8],
            'TOKEN': f"{self.peer.user_id}|{int(time.time())+3600}|game"
        }
        self.peer._send_message(payload, (opponent_ip, PORT))

        print(f"You played at position {position}.")
        game.display_board()
        win_message = game.check_win()
        if win_message:
            print(f"[GAME OVER] {win_message}")
            del self.peer.active_games[game_id]
        elif game.check_draw():
            print("[GAME OVER] The game is a draw!")
            del self.peer.active_games[game_id]
        else:
            print(f"Waiting for {opponent_id} to move.")
            
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