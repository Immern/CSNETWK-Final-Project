import socket

class TicTacToe:
    """
    Handles the Tic Tac Toe game logic, including sending invites and processing moves.
    """

    def __init__(self, player1_id, player2_id):
        self.players = {
            'X' : player1_id, 
            'O' : player2_id
        }
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        self.current_player_symbol = 'X'
        
    def display_board(self):
        for i in range(3):
            for j in range(3):
                print(f" {self.board[i][j]} ", end='')
                if j < 2:
                    print("|", end='')
                else:
                    print('\n')
            if i < 2:
                print("-----------")
            
    def make_move(self, player_id, row, col):
        if(self.players[self.current_player_symbol] != player_id):
            return False, (f"Error: It's not your turn, {player_id}.")
        if not (0 <= row < 3 and 0 <= col < 3):
            return False,"Error: Move out of bounds."
        if self.board[row][col] != ' ':
            return False, "Error: Cell already occupied."
        self.board[row][col] = self.current_player_symbol
        self.current_player_symbol = 'O' if self.current_player_symbol == 'X' else 'X'
        return True, "Move Successful."
        
    def check_win(self):
        for symbol in ['X', 'O']:
            # Check rows
            for row in self.board:
                if all(cell == symbol for cell in row):
                    return f"{symbol} wins!"
            # Check columns
            for col in range(3):
                if all(self.board[row][col] == symbol for row in range(3)):
                    return f"{symbol} wins!"
            # Check diagonals
            if all(self.board[i][i] == symbol for i in range(3)) or \
               all(self.board[i][2 - i] == symbol for i in range(3)):
                return f"{symbol} wins!"
            
    def check_draw(self):        
       return not any(' ' in row for row in self.board)

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
            # Check to prevent a user from inviting themselves
            if sender_id == peer.user_id:
                print(f"\n[Game Error] You cannot invite yourself to a game.")
                print(f"({peer.username}) > ", end='', flush=True)
                return
            peer.pending_game_invites[game_id] = message
            print(f"\n[New Game] {sender_id} is inviting you to play Tic Tac Toe on Game ID {game_id}.")
            print(f"({peer.username}) > ", end='', flush=True)
            
    def _handle_tictactoe_move(self, peer, message, addr):
        game_id = message.get('GAMEID')
        mover_id = message.get('FROM')
        position = int(message.get('POSITION'))
        row, col = position//3, position % 3
        
        game = peer.active_games.get(game_id)
        # Game just started
        if not game:
            invite_message = peer.pending_game_invites.get(game_id)
            print(f'handlers {invite_message}')
            if invite_message:
                inviter_id = invite_message['FROM']
                peer.active_games[game_id] = TicTacToe(inviter_id, mover_id)
                game = peer.active_games[game_id]
                # Remove the invite since the game is now active
                if game_id in peer.pending_game_invites:
                    del peer.pending_game_invites[game_id]
                print(f"\n[GAME START] Game {game_id} accepted and started by {mover_id}!")
            else:
                inviter_id = peer.user_id
                peer.active_games[game_id] = TicTacToe(mover_id, inviter_id)
                game = peer.active_games[game_id]
                print(f"\n[GAME ACCEPTED] Game {game_id} accepted by {mover_id}.")
        # Game is active
        if game:
            success, message = game.make_move(mover_id, row, col)
            if success:
                print(f"\n[Game Move] {mover_id} made a move at ({row}, {col}).")
                game.display_board()
                win_message = game.check_win()
                if win_message:
                    print(f"\n[Game Over] {win_message}")
                    del peer.active_games[game_id]
                elif game.check_draw():
                    print("\n[Game Over] It's a draw!")
                    del peer.active_games[game_id]
            else:
                print(f"\n[Game Error] {message} (from {mover_id})")
        else:
            if peer.verbose:
                print(f"[{peer.username}] Received a game move for a non-existent game: {game_id}")
        print(f"({peer.username}) > ", end='', flush=True)

