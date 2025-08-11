# LSNP Milestone 1 & 2 Test Plan

This document outlines a series of tests to verify the core functionality of your Local Social Networking Protocol (LSNP) implementation for Milestones 1 and 2.

**Testing Environment Setup:**
* **Peers:** You will need at least two peers running simultaneously. Let's call them **Peer A** and **Peer B**.
* **Network Mode:** Use the `simulate` mode for local testing.
    * Open two separate terminal windows.
    * **Terminal 1 (Peer A):** `python main.py Alice --mode simulate --ip 127.0.0.1`
    * **Terminal 2 (Peer B):** `python main.py Bob --mode simulate --ip 127.0.0.2`
* **User IDs:**
    * Peer A's User ID will be `Alice@127.0.0.1`
    * Peer B's User ID will be `Bob@127.0.0.2`

---

## Milestone 1: Basic Functionality Tests

### Test 1.1: Peer Initialization and Network Binding
* **Objective:** Verify that the LSNP peer starts without errors and binds to the correct port.
* **Steps:**
    1.  In each terminal, run the startup commands listed above.
* **Expected Outcome:**
    * Each peer should print an initialization message, its `USER_ID`, and that it is "Listening on port 50999...".
    * The application should not crash or show any "Could not bind to port" errors.
* **Rubric Reference:** Clean Architecture & Logging, Message Sending and Receiving.

### Test 1.2: Verbose Mode and Logging
* **Objective:** Ensure the `verbose` command toggles detailed logging for sent and received messages.
* **Steps:**
    1.  On **Peer A**, type `verbose` and press Enter.
    2.  On **Peer B**, type `profile Just setting up!` and press Enter.
* **Expected Outcome:**
    * **Peer A** should print a detailed log of the incoming `PROFILE` message from Peer B, including the raw message, the parsed dictionary, and the sender's address.
    * The output should look similar to:
        ```
        --- RECV from ('127.0.0.2', 50999) ---
        Raw: TYPE: PROFILE...
        Parsed: {'TYPE': 'PROFILE', ...}
        ------------------------
        ```
* **Rubric Reference:** Clean Architecture & Logging, Protocol Compliance Test Suite.

### Test 1.3: Message Parsing and Display
* **Objective:** Verify that the client can correctly parse all required message types and display stored data.
* **Steps:**
    1.  On **Peer A**, send a direct message to Peer B: `dm Bob@127.0.0.2 Hello Bob!`
    2.  On **Peer B**, check for known peers: `peers`
    3.  On **Peer B**, check for direct messages: `dms`
* **Expected Outcome:**
    * **Peer B** should display a notification: `[DM] From Alice@127.0.0.1: Hello Bob!`
    * The `peers` command on **Peer B** should list `Alice@127.0.0.1`.
    * The `dms` command on **Peer B** should list the message received from Alice.
* **Rubric Reference:** Protocol Parsing and Message Format.

---

## Milestone 2: User Discovery & Messaging Tests

### Test 2.1: Automatic User Discovery (PING/PROFILE)
* **Objective:** Ensure peers automatically discover each other via periodic presence broadcasts.
* **Steps:**
    1.  Start **Peer A** and **Peer B**.
    2.  Wait for at least 30 seconds (the current `PRESENCE_INTERVAL`).
    3.  On both peers, run the `peers` command.
* **Expected Outcome:**
    * Within 30 seconds, each peer should receive a `PING` and `PROFILE` message from the other.
    * **Peer A**'s `peers` list should contain `Bob@127.0.0.2`.
    * **Peer B**'s `peers` list should contain `Alice@127.0.0.1`.
    * Each peer should show a `[Discovery] New peer discovered...` message.
* **Rubric Reference:** User Discovery and Presence.

### Test 2.2: Follow and Post Logic (Correctness Check)
* **Objective:** Verify that the "follow" and "post" logic is implemented correctly. A user should only see posts from peers they are following.
* **Steps:**
    1.  On **Peer A**, follow Peer B: `follow Bob@127.0.0.2`
    2.  On **Peer B**, you should see a notification: `[Notification] User Alice@127.0.0.1 has followed you.`
    3.  On **Peer B**, make a post: `post This is a test post for my new follower!`
    4.  On **Peer A**, check for posts: `posts`
    5.  On **Peer A**, make a post: `post This is a post from Alice.`
    6.  On **Peer B**, check for posts: `posts`
* **Expected Outcome:**
    * **Peer A** should receive the `[New Post]` notification from Bob and see Bob's post when running the `posts` command.
    * **Peer B** should **NOT** receive a notification for Alice's post and should see "No posts received yet" (or only posts from others it follows) when running the `posts` command, because Bob is not following Alice.
* **Rubric Reference:** Messaging Functionality (POST, FOLLOW).

### Test 2.3: Unfollow Logic
* **Objective:** Verify that unfollowing a user stops their posts from being received.
* **Steps:**
    1.  Ensure **Peer A** is following **Peer B** (from the previous test).
    2.  On **Peer A**, unfollow Peer B: `unfollow Bob@127.0.0.2`
    3.  On **Peer B**, you should see a notification: `[Notification] User Alice@1.27.0.0.1 has unfollowed you.`
    4.  On **Peer B**, make a new post: `post Can Alice see this post?`
* **Expected Outcome:**
    * **Peer A** should **NOT** receive a `[New Post]` notification from Bob's new post.
    * Running `posts` on **Peer A** should only show the old posts from before the unfollow.
* **Rubric Reference:** Messaging Functionality (UNFOLLOW).

### Test 2.4: Direct Message (DM) Privacy
* **Objective:** Ensure DMs are sent via unicast and are only visible to the intended recipient.
* **Steps:**
    1.  Start a third peer, **Peer C**: `python main.py Charlie --mode simulate --ip 127.0.0.3`
    2.  On **Peer A**, send a DM to Peer B: `dm Bob@127.0.0.2 This is a private message.`
* **Expected Outcome:**
    * Only **Peer B** should receive the `[DM]` notification.
    * **Peer C** should not see any message traffic related to the DM between A and B, even in verbose mode.
* **Rubric Reference:** Messaging Functionality (DM).