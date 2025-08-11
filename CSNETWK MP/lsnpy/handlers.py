import socket
import time
import base64
import os
from lsnpy.core import PORT

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
            for i, row in enumerate(self.board):
                if all(cell == symbol for cell in row):
                    winline = [i*3, i*3 + 1, i*3 + 2]
                    return f"{self.players[symbol]} wins!", winline, symbol
            # Check columns
            for col in range(3):
                if all(self.board[row][col] == symbol for row in range(3)):
                    winline = [col, col + 3, col + 6]
                    return f"{self.players[symbol]} wins!", winline, symbol
            # Check diagonals
            if all(self.board[i][i] == symbol for i in range(3)):
                winline = [0, 4, 8]
                return f"{self.players[symbol]} wins!", winline, symbol
            if all(self.board[i][2 - i] == symbol for i in range(3)):
                winline = [2, 4, 6]
                return f"{self.players[symbol]} wins!", winline, symbol
        return None
            
    def check_draw(self):        
       return not any(' ' in row for row in self.board)

class LsnpMessageHandler:
    """
    Handles and processes incoming LSNP messages, updating the peer's state.
    """

    def __init__(self):
        self.handlers = {
            'PING': self._handle_ping,
            'PROFILE': self._handle_profile,
            'POST': self._handle_post,
            'DM': self._handle_dm,
            'FOLLOW': self._handle_follow,
            'UNFOLLOW': self._handle_unfollow,
            'LIKE': self._handle_like,
            'UNLIKE': self._handle_unlike,
            'GROUP_CREATE': self._handle_group_create,
            'GROUP_UPDATE': self._handle_group_update,
            'GROUP_MESSAGE': self._handle_group_message,
            'FILE_OFFER': self._handle_file_offer,
            'FILE_ACCEPT': self._handle_file_accept,
            'FILE_CHUNK': self._handle_file_chunk,
            'TICTACTOE_INVITE': self._handle_tictactoe_invite,
            'TICTACTOE_ACCEPT': self._handle_tictactoe_accept,
            'TICTACTOE_MOVE': self._handle_tictactoe_move,
            'TICTACTOE_RESULT': self._handle_tictactoe_result,
        }
        self.message_scopes = {
            'POST': 'broadcast',
            'LIKE': 'broadcast',
            'UNLIKE': 'broadcast',
            'DM': 'chat',
            'FOLLOW': 'follow',
            'UNFOLLOW': 'follow',
            'GROUP_CREATE': 'group',
            'GROUP_UPDATE': 'group',
            'GROUP_MESSAGE': 'group',
            'FILE_OFFER': 'file',
            'FILE_ACCEPT': 'file',
            'FILE_CHUNK': 'file',
            'TICTACTOE_INVITE': 'game',
            'TICTACTOE_ACCEPT': 'game',
            'TICTACTOE_MOVE': 'game',
            'TICTACTOE_RESULT': 'game',
        }

    def _validate_token(self, peer, message, expected_scope):
        token = message.get('TOKEN')
        if not token:
            return False, "Missing token"

        parts = token.split('|')
        if len(parts) != 3:
            return False, "Invalid token format"

        user_id, expiry, scope = parts
        if user_id != message.get('FROM', message.get('USER_ID')):
            return False, "Token user ID mismatch"

        if int(expiry) < time.time():
            return False, "Token expired"

        if scope != expected_scope:
            return False, f"Invalid token scope: expected '{expected_scope}', got '{scope}'"

        return True, "Token is valid"

    def handle(self, peer, data, addr):
        """Routes the incoming message to the correct handler method."""
        try:
            message_str = data.decode('utf-8')
            parsed_message = peer._parse_message(message_str)

            sender_id = parsed_message.get('USER_ID') or parsed_message.get('FROM')
            if sender_id == peer.user_id:
                return
            if parsed_message.get('TYPE') == 'ACK':
                return

            elif peer.verbose and parsed_message.get('TYPE') != 'ACK':
                ACK_payload = {
                    'TYPE': 'ACK',
                    'MESSAGE_ID': parsed_message.get('MESSAGE_ID'),
                    'STATUS': 'RECEIVED'
                }
                peer._send_message(ACK_payload, addr)
            
            msg_type = parsed_message.get('TYPE')
            handler_func = self.handlers.get(msg_type)
            if handler_func:
                if msg_type not in ['PING', 'PROFILE']:
                    expected_scope = self.message_scopes.get(msg_type)
                    if expected_scope:
                        is_valid, reason = self._validate_token(peer, parsed_message, expected_scope)
                        if not is_valid and parsed_message.get('TYPE') != 'TICTACTOE_RESULT':
                            print(f"\n[Security] Invalid token for {msg_type} from {sender_id}: {reason}")
                            print(f"\n({peer.username}) > ", end='', flush=True)
                            return
                
                handler_func(peer, parsed_message, addr)
            elif peer.verbose:
                print(f"[Ignored] Unknown message type: {parsed_message.get('TYPE')}")
                print(f"\n({peer.username}) > ", end='', flush=True)

        except (UnicodeDecodeError, ValueError) as e:
            print(f"\n[ERROR] Could not process message from {addr}: {e}")
            print(f"\n({peer.username}) > ", end='', flush=True)

    def _handle_ping(self, peer, message, addr):
        user_id = message.get('USER_ID')
        if user_id and user_id not in peer.known_peers:
            profile_payload = {
                'TYPE': 'PROFILE',
                'USER_ID': peer.user_id,
                'DISPLAY_NAME': peer.username,
                'STATUS': "Online",
                'TIMESTAMP': int(time.time())
            }
            peer._send_message(profile_payload, addr)
        if peer.verbose:
            print(f"\n[PING] Received from {user_id}")


    def _handle_profile(self, peer, message, addr):
        user_id = message.get('USER_ID', 'Unknown')
        display_name = message.get('DISPLAY_NAME', 'N/A')
        status = message.get('STATUS', 'N/A')
        manual = message.get('MANUAL', False)

        if not user_id or user_id == 'Unknown':
            return

        if user_id not in peer.known_peers:
            print(f"\n[Discovery] New peer discovered: {user_id}")
            print(f"\n({peer.username}) > ", end='', flush=True) 
        
        peer.known_peers[user_id] = message

        if peer.verbose:
            print(f"[PROFILE]")
            for key, value in message.items():
                print(f"{key}: {value}")
        else:
            if manual:
                print(f"[PROFILE] {display_name} - Status: {status}")
        
        if manual or peer.verbose:
            print(f"\n({peer.username}) > ", end='', flush=True)

    def _handle_post(self, peer, message, addr):
        sender_id = message.get('USER_ID')
        if sender_id in peer.following:
            peer.posts.append(message)
            print(f"\n[New Post] From {sender_id}: {message.get('CONTENT')}")
            print(f"({peer.username}) > ", end='', flush=True)
        elif peer.verbose:
            print(f"\n[Ignored Post] User {peer.user_id} is not following {sender_id}")
            print(f"\n({peer.username}) > ", end='', flush=True)

    def _handle_dm(self, peer, message, addr):
        if message.get('TO') == peer.user_id:
            peer.dms.append(message)
            sender_id = message.get('FROM')
            print(f"\n[DM] From {sender_id}: {message.get('CONTENT')}")
            print(f"\n({peer.username}) > ", end='', flush=True)

    def _handle_follow(self, peer, message, addr):
        if message.get('TO') == peer.user_id:
            sender_id = message.get('FROM')
            peer.followers.add(sender_id)
            print(f"\n[Notification] User {sender_id} has followed you.")
            print(f"\n({peer.username}) > ", end='', flush=True)
    
    def _handle_unfollow(self, peer, message, addr):
        if message.get('TO') == peer.user_id:
            sender_id = message.get('FROM')
            peer.followers.discard(sender_id)
            print(f"\n[Notification] User {sender_id} has unfollowed you.")
            print(f"\n({peer.username}) > ", end='', flush=True)

    def _handle_like(self, peer, message, addr):
        post_ts = message.get('POST_TIMESTAMP')
        sender_id = message.get('FROM')
        if message.get('TO') == peer.user_id:
            peer.likes.setdefault(post_ts, set()).add(sender_id)
            print(f"\n[Notification] {sender_id} liked your post.")
            print(f"\n({peer.username}) > ", end='', flush=True)

    def _handle_unlike(self, peer, message, addr):
        post_ts = message.get('POST_TIMESTAMP')
        sender_id = message.get('FROM')
        if message.get('TO') == peer.user_id:
            if post_ts in peer.likes:
                peer.likes[post_ts].discard(sender_id)
            print(f"\n[Notification] {sender_id} unliked your post.")
            print(f"\n({peer.username}) > ", end='', flush=True)

    def _handle_group_create(self, peer, message, addr):
        if peer.user_id in message.get('MEMBERS', ''):
            group_id = message.get('GROUP_ID')
            peer.groups[group_id] = message
            print(f"\n[Notification] You've been added to group: {message.get('GROUP_NAME')}")
            print(f"\n({peer.username}) > ", end='', flush=True)

    def _handle_group_update(self, peer, message, addr):
        group_id = message.get('GROUP_ID')
        new_members_list = message.get('MEMBERS', '').split(',')
        group_name = message.get('GROUP_NAME')

        if peer.user_id in new_members_list:
            if group_id not in peer.groups:
                print(f"\n[Notification] You have been added to group: {group_name}")
            else:
                print(f"\n[Notification] Group '{group_name}' has been updated.")

            peer.groups[group_id] = message
            print(f"\n({peer.username}) > ", end='', flush=True)

        elif group_id in peer.groups:
            print(f"\n[Notification] You have been removed from group: {group_name}")
            del peer.groups[group_id]
            print(f"\n({peer.username}) > ", end='', flush=True)

    def _handle_group_message(self, peer, message, addr):
        group_id = message.get('GROUP_ID')
        if group_id in peer.groups:
            if peer.user_id in peer.groups[group_id].get('MEMBERS', ''):
                group_name = peer.groups[group_id].get('GROUP_NAME', group_id)
                sender_id = message.get('FROM')
                content = message.get('CONTENT')
                print(f"\n[Group: '{group_name}'] {sender_id}: {content}")
                print(f"\n({peer.username}) > ", end='', flush=True)
            
    def _handle_file_offer(self, peer, message, addr):
        if message.get('TO') == peer.user_id:
            file_id = message.get('FILEID')
            sender_id = message.get('FROM')
            filename = message.get('FILENAME')
            filesize = message.get('FILESIZE')
            
            print(f"\n[File Offer] {sender_id} wants to send you '{filename}' ({filesize} bytes).")
            print(f"Type 'file_accept {file_id}' to accept.")
            print(f"\n({peer.username}) > ", end='', flush=True)
            
            peer.file_transfers[file_id] = {
                'info': message,
                'chunks': {},
                'received_chunks': 0
            }

    def _handle_file_accept(self, peer, message, addr):
        file_id = message.get('FILEID')
        if file_id in peer.file_transfers:
            transfer_info = peer.file_transfers[file_id]
            file_path = transfer_info.get('path')
            if not file_path:
                return

            print(f"\n[File] {message.get('FROM')} accepted your file offer. Sending chunks...")
            print(f"\n({peer.username}) > ", end='', flush=True)
            
            with open(file_path, "rb") as f:
                data = f.read()
                
            b64_data = base64.b64encode(data).decode('utf-8')
            chunk_size = 1024
            chunks = [b64_data[i:i+chunk_size] for i in range(0, len(b64_data), chunk_size)]
            
            recipient_id = message.get('FROM')
            recipient_ip = peer.get_recipient_ip(recipient_id)
            
            ts = int(time.time())
            for i, chunk in enumerate(chunks):
                payload = {
                    'TYPE': 'FILE_CHUNK',
                    'FROM': peer.user_id,
                    'TO': recipient_id,
                    'FILEID': file_id,
                    'CHUNK_INDEX': i,
                    'TOTAL_CHUNKS': len(chunks),
                    'DATA': chunk,
                    'TIMESTAMP': ts,
                    'TOKEN': f"{peer.user_id}|{ts+3600}|file"
                }
                peer._send_message(payload, (recipient_ip, PORT))
                time.sleep(0.01)
                
            print(f"All chunks for file '{transfer_info['info']['FILENAME']}' have been sent.")
            print(f"\n({peer.username}) > ", end='', flush=True)
            del peer.file_transfers[file_id]
            
    def _handle_file_chunk(self, peer, message, addr):
        file_id = message.get('FILEID')
        if file_id in peer.file_transfers:
            transfer = peer.file_transfers[file_id]
            
            chunk_index = int(message.get('CHUNK_INDEX'))
            total_chunks = int(message.get('TOTAL_CHUNKS'))
            data = message.get('DATA')
            
            if chunk_index not in transfer['chunks']:
                transfer['chunks'][chunk_index] = data
                transfer['received_chunks'] += 1
                
                if peer.verbose:
                    print(f"\n[File] Received chunk {chunk_index + 1}/{total_chunks} for file {file_id}")
                    
                if transfer['received_chunks'] == total_chunks:
                    sorted_chunks = [transfer['chunks'][i] for i in sorted(transfer['chunks'].keys())]
                    file_data_b64 = "".join(sorted_chunks)
                    file_data = base64.b64decode(file_data_b64)
                    
                    filename = transfer['info'].get('FILENAME')
                    with open(f"received_{filename}", "wb") as f:
                        f.write(file_data)
                        
                    print(f"\n[File] Transfer of '{filename}' complete!")
                    print(f"\n({peer.username}) > ", end='', flush=True)
                    
                    del peer.file_transfers[file_id]

    def _handle_tictactoe_invite(self, peer, message, addr):
        if message.get('TO') == peer.user_id:
            game_id = message.get('GAMEID')
            sender_id = message.get('FROM')
            
            if sender_id == peer.user_id:
                print(f"\n[Game Error] You cannot invite yourself to a game.")
                print(f"\n({peer.username}) > ", end='', flush=True)
                return

            peer.pending_game_invites[game_id] = message
            print(f"\n[New Game] {sender_id} is inviting you to play Tic Tac Toe (Game ID: {game_id}).")
            print(f"Type 'tictactoe_accept {game_id}' to play.")
            print(f"\n({peer.username}) > ", end='', flush=True)

    def _handle_tictactoe_accept(self, peer, message, addr):
        """Handles the confirmation of a game invite."""
        game_id = message.get('GAMEID')
        acceptor_id = message.get('FROM')

        invite = peer.pending_game_invites.get(game_id)
        if not invite or invite.get('FROM') != peer.user_id:
            return

        peer.active_games[game_id] = TicTacToe(peer.user_id, acceptor_id)
        game = peer.active_games[game_id]

        del peer.pending_game_invites[game_id]

        print(f"\n[Game START] {acceptor_id} has accepted your game invite for {game_id}!")
        game.display_board()
        print("It's your turn. Use 'tictactoe_move'.")
        print(f"\n({peer.username}) > ", end='', flush=True)
            
    def _handle_tictactoe_move(self, peer, message, addr):
        """Handles a game move for an already active game."""
        game_id = message.get('GAMEID')
        mover_id = message.get('FROM')
        
        game = peer.active_games.get(game_id)
        if not game:
            if peer.verbose:
                print(f"[{peer.username}] Received a game move for a non-existent or inactive game: {game_id}")
            return

        position = int(message.get('POSITION'))
        row, col = position // 3, position % 3

        success, response_message = game.make_move(mover_id, row, col)
        if success:
            print(f"\n[Game Move] {mover_id} played at position {position}.")
            game.display_board()
            game_result = game.check_win()
            if game_result: 
                win_message, win_line, win_symbol = game_result 
            if game_result and win_message:
                print(f"\n[Game Over] {win_message}")
                del peer.active_games[game_id]
            elif game.check_draw():
                print("\n[Game Over] The game is a draw!")
                del peer.active_games[game_id]
            else:
                print("It's your turn.")
        else:
            print(f"\n[Game Error] {response_message} (from {mover_id})")

        print(f"\n({peer.username}) > ", end='', flush=True)
        
    def _handle_tictactoe_result(self, peer, message, addr):
        game_id = message.get('GAMEID')
        if game_id in peer.active_games:
            result = message.get('RESULT')
            winner = message.get('WINNER')
            print(f"\n[Game Over] Game {game_id} ended. Result: {result}, Winner: {winner}")
            del peer.active_games[game_id]
        print(f"\n({peer.username}) > ", end='', flush=True)