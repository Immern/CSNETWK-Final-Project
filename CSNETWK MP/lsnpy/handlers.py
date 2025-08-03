import socket

class LsnpMessageHandler:
    """
    Handles and processes incoming LSNP messages, updating the peer's state.
    """

    def __init__(self):
        # A dictionary to map message types to handler methods
        self.handlers = {
            'PROFILE': self._handle_profile,
            'POST': self._handle_post,
            'DM': self._handle_dm,
            'FOLLOW': self._handle_follow,
            'UNFOLLOW': self._handle_unfollow,
            'LIKE': self._handle_like,
            'GROUP_CREATE': self._handle_group_create,
            'GROUP_MESSAGE': self._handle_group_message,
            'TICTACTOE_INVITE': self._handle_tictactoe_invite,
            'TICTACTOE_MOVE': self._handle_tictactoe_move,     
        }
        # dictionary mapping scope types to message handlers to be used for validation
        self.message_scopes = {
            'PROFILE': 'broadcast',
            'POST': 'broadcast',
            'LIKE': 'broadcast',
            'DM': 'chat',
            'FOLLOW': 'follow',
            'UNFOLLOW': 'follow',
            'GROUP_CREATE': 'group',
            'GROUP_MESSAGE': 'group',
            'TICTACTOE_INVITE': 'game',
            'TICTACTOE_MOVE': 'game',
        }

    def handle(self, peer, data, addr):
        """Routes the incoming message to the correct handler method."""
        try:
            message_str = data.decode('utf-8')
            parsed_message = peer._parse_message(message_str)

            sender_id = parsed_message.get('USER_ID') or parsed_message.get('FROM')
            if sender_id == peer.user_id:
                return

            if peer.verbose:
                print(f"\n--- RECV from {addr} ---")
                print(f"Raw: {message_str.strip()}")
                print(f"Parsed: {parsed_message}")
                print("------------------------")

            msg_type = parsed_message.get('TYPE')
            handler_func = self.handlers.get(msg_type)
            if handler_func:
                handler_func(peer, parsed_message, addr)
            elif peer.verbose:
                print(f"[Ignored] Unknown message type: {msg_type}")

        except (UnicodeDecodeError, ValueError) as e:
            print(f"\n[ERROR] Could not process message from {addr}: {e}")

    def _handle_profile(self, peer, message, addr):
        user_id = message.get('USER_ID')
        if user_id and user_id not in peer.known_peers:
            print(f"\n[Discovery] New peer discovered: {user_id}")
            print(f"({peer.username}) > ", end='', flush=True)
            peer.known_peers[user_id] = message
        elif user_id:
            peer.known_peers[user_id] = message

    def _handle_post(self, peer, message, addr):
        sender_id = message.get('USER_ID')
        if sender_id in peer.following:
            peer.posts.append(message)
            print(f"\n[New Post] From {sender_id}: {message.get('CONTENT')}")
            print(f"({peer.username}) > ", end='', flush=True)
        elif peer.verbose:
            print(f"\n[Ignored Post] From non-followed user: {sender_id}")

    def _handle_dm(self, peer, message, addr):
        if message.get('TO') == peer.user_id:
            peer.dms.append(message)
            sender_id = message.get('FROM')
            print(f"\n[DM] From {sender_id}: {message.get('CONTENT')}")
            print(f"({peer.username}) > ", end='', flush=True)

    def _handle_follow(self, peer, message, addr):
        if message.get('TO') == peer.user_id:
            sender_id = message.get('FROM')
            peer.followers.add(sender_id)
            print(f"\n[Notification] User {sender_id} has followed you.")
            print(f"({peer.username}) > ", end='', flush=True)
    
    def _handle_unfollow(self, peer, message, addr):
        if message.get('TO') == peer.user_id:
            sender_id = message.get('FROM')
            peer.followers.discard(sender_id)
            print(f"\n[Notification] User {sender_id} has unfollowed you.")
            print(f"({peer.username}) > ", end='', flush=True)

    def _handle_like(self, peer, message, addr):
        if message.get('TO') == peer.user_id:
            sender_id = message.get('FROM')
            print(f"\n[Notification] {sender_id} liked your post.")
            print(f"({peer.username}) > ", end='', flush=True)

    def _handle_group_create(self, peer, message, addr):
        if peer.user_id in message.get('MEMBERS', ''):
            group_id = message.get('GROUP_ID')
            peer.groups[group_id] = message
            print(f"\n[Notification] You've been added to group: {message.get('GROUP_NAME')}")
            print(f"({peer.username}) > ", end='', flush=True)

    def _handle_group_message(self, peer, message, addr):
        group_id = message.get('GROUP_ID')
        if group_id in peer.groups:
            sender_id = message.get('FROM')
            print(f"\n[Group Message] {sender_id}: {message.get('CONTENT')}")
            print(f"({peer.username}) > ", end='', flush=True)

    def _handle_tictactoe_invite(self, peer, message, addr):
        if message.get('TO') == peer.user_id:
            game_id = message.get('GAMEID')
            sender_id = message.get('FROM')
            peer.pending_game_invites[game_id] = message
            print(f"\n[New Game] {sender_id} is inviting you to play Tic Tac Toe on Game ID {game_id}.")
            print(peer.pending_game_invites)
            print(f"({peer.username}) > ", end='', flush=True)
            
    def _handle_tictactoe_move(self, peer, message, addr):
        game_id = message.get('GAMEID')
        mover_id = message.get('FROM')
        position = int(message.get('POSITION'))
        
        # Check if this is the first move (the one that accepts the game)
        game = peer.active_games.get(game_id)
        if not game:
            invite_message = peer.pending_game_invites.get(game_id)
            if invite_message and mover_id != peer.user_id:
                inviter_id = invite_message['FROM']
                peer.active_games[game_id] = 'new game'  # Placeholder for game state
                game = peer.active_games[game_id]
                # Remove the invite since the game is now active
                del peer.pending_game_invites[game_id]
                print(f"\n[GAME START] Game {game_id} accepted and started by {mover_id}!")

        # [INSERT GAME LOGIC HERE]
