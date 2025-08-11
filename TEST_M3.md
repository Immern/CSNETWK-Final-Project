# LSNP Milestone 3 Test Plan

This document outlines tests for the advanced features of the Local Social Networking Protocol (LSNP) implementation for Milestone 3.

***

## Testing Environment Setup:

* **Peers:** You will need at least three peers running simultaneously. Let's call them **Peer A**, **Peer B**, and **Peer C**.
* **Network Mode:** Use the `simulate` mode for local testing.
    * Open three separate terminal windows.
    * **Terminal 1 (Peer A):** `python main.py Alice --mode simulate --ip 127.0.0.1`
    * **Terminal 2 (Peer B):** `python main.py Bob --mode simulate --ip 127.0.0.2`
    * **Terminal 3 (Peer C):** `python main.py Charlie --mode simulate --ip 127.0.0.3`
* **User IDs:**
    * Peer A: `Alice@127.0.0.1`
    * Peer B: `Bob@127.0.0.2`
    * Peer C: `Charlie@127.0.0.3`
* **Required Files:**
    * Create a small image file named `avatar.png` in your project directory.
    * Create a text file named `testfile.txt` with the content "Hello LSNP file transfer!"

***

## Milestone 3: Advanced Functionality Tests

### Test 3.1: Profile Picture and Likes

* **Objective:** Verify that peers can broadcast profiles with avatars and that the like functionality works as expected.
* **Steps:**
    1.  On **Peer A**, follow **Peer B**: `follow Bob@127.0.0.2`
    2.  On **Peer B**, broadcast a post. Note the timestamp that is printed (e.g., 1728938391). Command: `post Hello everyone!`
    3.  On **Peer A**, like the post from **Peer B** using the timestamp from the previous step: `like Bob@127.0.0.2 <timestamp>`
    4.  On **Peer C**, update profile with an avatar: `profile "Enjoying the network" avatar.png`
    5.  On **Peer A** and **Peer B**, run `peers` to check the updated peer list.
* **Expected Outcome:**
    * **Peer B** should receive a notification: `[Notification] Alice@127.0.0.1 liked your post.`
    * The `profile` command on **Peer C** should broadcast successfully.
    * The `peers` command on A and B should still list all peers, and the internal data for **Peer C** should now contain the avatar information (verifiable in verbose mode).
* **Rubric Reference:** Profile Picture and Likes.

***

### Test 3.2: Token Handling and Scope Validation

* **Objective:** Ensure that the server correctly rejects messages with invalid or mismatched tokens.
* **Steps:**
    1.  This test requires a temporary modification to the code to simulate a bad token.
    2.  In `lsnpy/cli.py`, find the `_send_dm_command` method.
    3.  Change the TOKEN scope from `chat` to `game`: `'TOKEN': f"{self.peer.user_id}|{ts+3600}|game"`
    4.  Restart **Peer A** and **Peer B**.
    5.  On **Peer A**, attempt to send a DM to **Peer B**: `dm Bob@127.0.0.2 "Testing bad token"`
* **Expected Outcome:**
    * **Peer B**'s console should display a security warning: `[Security] Invalid token for DM from Alice@127.0.0.1: Invalid token scope: expected 'chat', got 'game'.`
    * The DM should not be processed or displayed.
    * **Remember to revert the code change after this test.**
* **Rubric Reference:** Token Handling and Scope Validation.

***

### Test 3.3: Group Management

* **Objective:** Verify the creation, updating, and messaging of groups.
* **Steps:**
    1.  On **Peer A**, create a new group: `group create studygroup "CSNETWK Study Group"`
    2.  On **Peer A**, update the group to add **Peer B**: `group update studygroup add Bob@127.0.0.2`
    3.  On **Peer A**, update the group to add **Peer C**: `group update studygroup add Charlie@127.0.0.3`
    4.  On **Peer B** and **Peer C**, they should receive notifications about being added to the group.
    5.  On **Peer B**, send a message to the group: `group msg studygroup "When is the deadline?"`
    6.  On **Peer A** and **Peer C**, check for the group message.
    7.  On all peers, run the `groups` command.
* **Expected Outcome:**
    * **Peer A** and **Peer C** should see the message from **Peer B**: `[Group: 'CSNETWK Study Group'] Bob@127.0.0.2: When is the deadline?`
    * The `groups` command on all three peers should list the `studygroup` with all three members.
* **Rubric Reference:** Group Management.

***

### Test 3.4: File Transfer

* **Objective:** Verify the end-to-end file transfer functionality.
* **Steps:**
    1.  On **Peer A**, offer to send `testfile.txt` to **Peer B**: `file_offer Bob@127.0.0.2 testfile.txt`
    2.  **Peer B** should receive a notification: `[File Offer] Alice@127.0.0.1 wants to send you 'testfile.txt'...`
    3.  Note the `file_id` from the offer.
    4.  On **Peer B**, accept the file offer: `file_accept <file_id>`
* **Expected Outcome:**
    * **Peer A** will receive the acceptance and begin sending file chunks (visible in verbose mode).
    * **Peer B** will receive the chunks and, upon completion, print: `[File] Transfer of 'testfile.txt' complete!`
    * A new file named `received_testfile.txt` should appear in the project directory, and its content should match the original file.
* **Rubric Reference:** File Transfer.

***

### Test 3.5: Game Support (Tic-Tac-Toe)

* **Objective:** Verify the complete game flow from invitation to a win/draw result.
* **Steps:**
    1.  On **Peer A**, invite **Peer B** to a game: `tictactoe_invite Bob@127.0.0.2`
    2.  **Peer B** should receive the invitation. Note the `game_id`.
    3.  On **Peer B**, accept the invitation: `tictactoe_accept <game_id>`
    4.  Both peers should see the game start. It is **Peer A**'s turn.
    5.  On **Peer A**, make a move: `tictactoe_move <game_id> 0`
    6.  On **Peer B**, make a move: `tictactoe_move <game_id> 4`
    7.  On **Peer A**, make a move: `tictactoe_move <game_id> 1`
    8.  On **Peer B**, make a move: `tictactoe_move <game_id> 5`
    9.  On **Peer A**, make the winning move: `tictactoe_move <game_id> 2`
* **Expected Outcome:**
    * Each move should be reflected on both players' boards.
    * After the final move, both peers should see: `[Game Over] Alice@127.0.0.1 wins!`
    * The game should be removed from the active games list on both peers.
* **Rubric Reference:** Game Support (Tic Tac Toe).