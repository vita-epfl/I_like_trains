import socket
import json
import threading
import time
import logging
import uuid
import signal
import random
from common import stats_manager
from common.config import Config
from server.passenger import Passenger
from server.room import Room
from common.version import EXPECTED_CLIENT_VERSION
from server.train import BOOST_COOLDOWN_DURATION


def setup_server_logger():
    # Create a handler for the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Define the format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)

    # Configure the main server logger
    server_logger = logging.getLogger("server")
    server_logger.setLevel(logging.DEBUG)
    server_logger.propagate = False
    server_logger.addHandler(console_handler)

    # Configure the loggers of the sub-modules
    modules = [
        "server.room",
        "server.game",
        "server.train",
        "server.passenger",
        "server.delivery_zone",
        "server.ai_client",
        "server.ai_agent",
    ]
    for module in modules:
        logger = logging.getLogger(module)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.addHandler(console_handler)

    return server_logger


# Configure the server logger
logger = setup_server_logger()


class Server:
    def __init__(self, config: Config):
        self.config = config.server
        self.rooms = {}  # {room_id: Room}
        self.lock = threading.Lock()

        host = self.config.host

        # Create UDP socket with proper error handling
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((host, self.config.port))
            logger.info(f"UDP socket created and bound to {host}:{self.config.port}")
        except Exception as e:
            logger.error(f"Error creating UDP socket: {e}")
            raise

        self.running = True

        self.addr_to_name = {}  # Maps client addresses to agent names
        self.addr_to_sciper = {}  # Maps client addresses to scipers
        self.addr_to_game_mode = {}  # Maps client addresses to game modes
        self.sciper_to_addr = {}  # Maps scipers to client addresses
        self.client_last_activity = {}  # Maps client addresses to last activity timestamp
        self.disconnected_clients = (
            set()
        )  # Track disconnected clients by full address tuple (IP, port)
        self.threads = []  # Initialize threads attribute

        # Ping tracking for active connection checking
        self.ping_interval = self.config.client_timeout_seconds / 2
        self.ping_responses = {}  # Track which clients have responded to pings

        # Start the ping thread (handles all client timeouts)
        self.ping_thread = threading.Thread(target=self.ping_clients)
        self.ping_thread.daemon = True
        self.ping_thread.start()

        # Create the first room
        self.create_room(True)

        # Start accepting clients
        accept_thread = threading.Thread(target=self.accept_clients, daemon=True)
        accept_thread.start()
        logger.info(f"Server started on {self.config.host}:{self.config.port}")

    def create_room(self, running):
        """
        Create a new room with specified number of clients
        """
        room_id = str(uuid.uuid4())[:8]

        nb_players_per_room = self.config.nb_clients_per_room
        logger.info(f"Creating room {room_id} with size {nb_players_per_room}.")

        new_room = Room(
            self.config,
            room_id,
            nb_players_per_room,
            running,
            self.server_socket,
            self.send_cooldown_notification,
            self.remove_room,
            self.addr_to_sciper,
            self.record_disconnection,
        )

        logger.info(f"Created new room {room_id} with {nb_players_per_room} clients")
        self.rooms[room_id] = new_room
        return new_room

    def get_available_room(self):
        """Get an available room or create a new one if needed"""
        # First try to find a non-full room
        for room in self.rooms.values():
            if (
                room.nb_players_max == self.config.nb_clients_per_room
                and not room.is_full()
                and not room.game_thread
            ):
                return room
        logger.debug(
            f"No suitable room found for {self.config.nb_clients_per_room} clients"
        )
        # If no suitable room found, create a new one
        return self.create_room(True)

    def accept_clients(self):
        """Thread that waits for new connections"""
        logger.info("Server is listening for UDP packets")
        error_count = {}  # Track error count per client

        while self.running:
            # TODO RESTORE
            try:
                # Receive data from any client
                data, addr = self.server_socket.recvfrom(1024)

                # If we successfully received data from this client, reset their error count
                if addr in error_count:
                    error_count[addr] = 0

                if not data:
                    continue

                data_str = data.decode()

                # Process the incoming message
                if data_str:
                    # Handle multiple messages in one packet
                    messages = data_str.split("\n")
                    for message_str in messages:
                        if not message_str:
                            continue

                        message = json.loads(message_str)
                        # Process the message
                        self.process_message(message, addr)
            except socket.error as e:
                # For UDP, we don't know which client caused the error
                # So we only log the error and don't mark any client as disconnected
                if "10054" in str(e):
                    # This is a connection reset error, which is expected in UDP
                    # We'll just log it at a lower level or not at all
                    pass  # Don't log connection reset errors at all
                else:
                    logger.error(f"Socket error: {e}")
                # Add a small delay to avoid high CPU usage on error
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in accept_clients: {e}")
                # Add a small delay to avoid high CPU usage on error
                time.sleep(0.1)

    def find_client_room(self, agent_sciper):
        for room in self.rooms.values():
            for addr in room.clients:
                if (
                    addr in self.addr_to_sciper
                    and self.addr_to_sciper[addr] == agent_sciper
                ):
                    return room
        return None

    def process_message(self, message, addr):
        """Process incoming messages from clients"""
        if addr in self.disconnected_clients:
            # Remove the client from the disconnected clients list
            self.disconnected_clients.remove(addr)

        # # Check if client's game-mode is observer
        if (
            "type" in message
            and message["type"] == "agent_ids"
            and "nickname" in message
            and "agent_sciper" in message
            and "game_mode" in message
            and addr not in self.addr_to_name
        ):
            if message["game_mode"] != "observer":
                # use handle_name_check and handle_sciper_check to check if the name and sciper are available
                logger.debug(
                    f"Checking name and sciper availability for {message['nickname']} ({message['agent_sciper']})"
                )
                if self.handle_name_check(message, addr) and self.handle_sciper_check(
                    message, addr
                ):
                    self.handle_new_client(message, addr)
            else:
                self.client_last_activity[addr] = time.time()
                self.handle_new_client(message, addr)
                return

        # Handle ping responses for everyone
        if "type" in message and message["type"] == "pong":
            self.client_last_activity[addr] = time.time()
            # Client has responded to a ping, update the ping responses dictionary
            if addr in self.ping_responses:
                del self.ping_responses[addr]  # Remove from pending responses
            return

        # Handle ping messages from unknown clients (for connection verification)
        if "type" in message and message["type"] == "ping":
            # Send a pong response even to unknown clients for connection verification
            pong_message = {"type": "pong"}
            try:
                self.server_socket.sendto(
                    (json.dumps(pong_message) + "\n\n").encode(), addr
                )
                return
            except Exception as e:
                logger.error(f"Error sending pong to {addr}: {e}")
                return

        agent_sciper = self.addr_to_sciper.get(addr)

        if agent_sciper:
            # Find which room this client belongs to
            client_room = self.find_client_room(agent_sciper)
            if client_room:
                self.handle_client_message(addr, message, client_room)
        else:
            self.handle_client_message(addr, message, None)

    def send_disconnect(self, addr, message="Unknown client or invalid message format"):
        """Disconnect a client from the server"""
        logger.debug(f"Sending disconnect request to unknown client {addr}")
        # ask the client to disconnect
        disconnect_message = {
            "type": "disconnect",
            "reason": message,
        }
        try:
            self.server_socket.sendto(
                (json.dumps(disconnect_message) + "\n").encode(), addr
            )
            logger.info(f"Sent disconnect request to unknown client {addr}")
        except Exception as e:
            logger.error(f"Error sending disconnect request to {addr}: {e}")

    # def handle_high_scores_request(self, addr):
    #     """Handle a request for high scores"""
    #     # Sort scores in descending order
    #     sorted_scores = sorted(
    #         self.high_score.get().items(), key=lambda x: x[1], reverse=True
    #     )
    #     top_scores = sorted_scores[:10]  # Get top 10 scores

    #     # Create response
    #     response = {
    #         "type": "high_scores",
    #         "scores": [
    #             {"sciper": sciper, "score": score} for sciper, score in top_scores
    #         ],
    #     }

    #     try:
    #         self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
    #         logger.info(f"Sent high scores to client at {addr}")
    #     except Exception as e:
    #         logger.error(f"Error sending high scores: {e}")

    def handle_name_check(self, message, addr):
        """Handle name check requests"""

        name_to_check = message.get("nickname", "")
        if addr:
            if not name_to_check or len(name_to_check) == 0 or len(name_to_check) > 15:
                # Empty name, considered as not available
                response = {"type": "name_check", "available": False}

                try:
                    self.server_socket.sendto(
                        (json.dumps(response) + "\n").encode(), addr
                    )
                except Exception as e:
                    logger.error(f"Error sending name check response: {e}")
                return False

        # Check if the name exists in any room
        name_available = True
        room = None  # Initialize room to None to avoid reference error

        for room_id, current_room in self.rooms.items():
            room = current_room  # Keep a reference to the last room
            for client_addr, nickname in current_room.clients.items():
                if nickname == name_to_check:
                    # Check if the client with this name is in disconnected_clients
                    if client_addr in self.disconnected_clients:
                        # Client is disconnected, name can be reused
                        logger.debug(
                            f"Name '{name_to_check}' found in room {room_id} but client is disconnected, considering it available"
                        )
                        continue
                    # Client is connected, name is not available
                    name_available = False
                    logger.debug(f"Name '{name_to_check}' found in room {room_id}")
                    break
            if not name_available:
                break

        # Check if name not in the ai names (only if we have at least one room)
        if room and name_available and name_to_check in room.AI_NAMES:
            name_available = False

        # Check if name starts with "Bot " (invalid)
        if name_available and name_to_check.startswith("Bot "):
            name_available = False
            logger.debug(f"Name '{name_to_check}' starts with 'Bot ', not available")

        if addr:
            response = {"type": "name_check", "available": name_available}

            try:
                self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
            except Exception as e:
                logger.error(f"Error sending name check response: {e}")

        return name_available

    def handle_sciper_check(self, message, addr):
        """Handle sciper check requests"""
        # Update client activity timestamp
        # self.client_last_activity[addr] = time.time()
        logger.debug(f"Checking sciper availability for {message['agent_sciper']}")

        sciper_to_check = message.get("agent_sciper", "")

        # Check if the sciper is empty or not an int
        if (
            not sciper_to_check
            or len(sciper_to_check) != 6
            or not sciper_to_check.isdigit()
        ):
            if addr:
                # Empty sciper, considered as not available
                response = {"type": "sciper_check", "available": False}
                try:
                    self.server_socket.sendto(
                        (json.dumps(response) + "\n").encode(), addr
                    )
                except Exception as e:
                    logger.error(f"Error sending sciper check response: {e}")
                return False
            else:
                return False

        if addr:
            response = {"type": "sciper_check", "available": True}

            try:
                self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
                logger.info(f"Sciper check for '{sciper_to_check}': available")
            except Exception as e:
                logger.error(f"Error sending sciper check response: {e}")

        return True

    def handle_new_client(self, message, addr):
        """Handle new client connection"""

        nickname = message.get("nickname", "")
        agent_sciper = message.get("agent_sciper", "")
        game_mode = message.get("game_mode", "")

        logger.debug(f"Received agent ids: {nickname}, {agent_sciper}, {game_mode}")

        if game_mode == "observer":
            logger.info(f"New client connected in OBSERVER mode: {addr}")
            self.client_last_activity[addr] = time.time()

            # generate a random name and sciper
            nickname = f"Observer_{random.randint(1000, 9999)}"
            agent_sciper = str(random.randint(100000, 999999))

        # Associate address with name and sciper
        self.addr_to_name[addr] = nickname
        self.addr_to_sciper[addr] = agent_sciper
        self.addr_to_game_mode[addr] = game_mode
        self.sciper_to_addr[agent_sciper] = addr

        # else:
        if not nickname:
            logger.warning("No agent name provided")
            return

        if not agent_sciper:
            logger.warning("No agent sciper provided")
            return

        logger.info(
            f"New client {nickname} (sciper: {agent_sciper}) connecting from {addr}"
        )

        # --- Record Connection Stats ---
        stats_manager.record_connection(agent_sciper, nickname)

        # Initialize client activity tracking
        self.client_last_activity[addr] = time.time()

        # Check if this sciper was previously connected and clean up any old references
        if agent_sciper in self.sciper_to_addr:
            old_addr = self.sciper_to_addr[agent_sciper]
            if old_addr != addr:  # Only if it's a different address
                logger.info(
                    f"Cleaning up previous connection for sciper {agent_sciper} at {old_addr}"
                )
                # Remove from disconnected_clients if present
                if old_addr in self.disconnected_clients:
                    self.disconnected_clients.remove(old_addr)
                # Clean up other mappings
                if old_addr in self.addr_to_name:
                    del self.addr_to_name[old_addr]
                if old_addr in self.addr_to_sciper:
                    del self.addr_to_sciper[old_addr]
                if old_addr in self.addr_to_game_mode:
                    del self.addr_to_game_mode[old_addr]
                if old_addr in self.client_last_activity:
                    del self.client_last_activity[old_addr]
                if old_addr in self.ping_responses:
                    del self.ping_responses[old_addr]

        # Remove from disconnected_clients if present (just in case)
        if addr in self.disconnected_clients:
            self.disconnected_clients.remove(addr)

        # Assign to a room
        selected_room = self.get_available_room()
        selected_room.clients[addr] = nickname
        selected_room.client_game_modes[addr] = game_mode

        # Mark the room as having at least one human player
        selected_room.has_clients = True

        # Record the time the first client joined this room
        if selected_room.first_client_join_time is None:
            selected_room.first_client_join_time = time.time()

        logger.info(
            f"Agent {nickname} (sciper: {agent_sciper}) joined room {selected_room.id}"
        )

        # Send join success response immediately
        response = {
            "type": "join_success",
            "expected_version": EXPECTED_CLIENT_VERSION
        }
        self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
        game_status = {
            "type": "waiting_room",
            "data": {
                "room_id": selected_room.id,
                "players": list(selected_room.clients.values()),
                "nb_players": selected_room.nb_players_max,
                "game_started": selected_room.game_thread is not None,
                "waiting_time": int(
                    max(
                        0,
                        self.config.waiting_time_before_bots_seconds
                        - (time.time() - selected_room.room_creation_time),
                    )
                )
                if selected_room.has_clients
                else 0,
            },
        }
        self.server_socket.sendto((json.dumps(game_status) + "\n").encode(), addr)

    def handle_client_message(self, addr, message, room=None):
        """Handles messages received from the client"""
        try:
            # Update client activity timestamp

            if room is None:
                # If room is None, we can't handle most messages
                if message.get("action") == "check_name":
                    self.handle_name_check(message, addr)
                    return

                if message.get("action") == "check_sciper":
                    self.handle_sciper_check(message, addr)
                    return

                # For other message types, we need a valid room
                logger.debug(
                    f"Ignoring message from client {addr} as they are not in any room: {message}. Sending disconnect message"
                )
                self.handle_client_disconnection(addr, "Unknown client")
                return

            nickname = room.clients.get(addr)
            if message.get("action") == "check_name":
                self.handle_name_check(message, addr)
                return

            if message.get("action") == "check_sciper":
                self.handle_sciper_check(message, addr)
                return

            self.client_last_activity[addr] = time.time()

            if message.get("action") == "respawn":
                # Check if the game is over
                if room.game_over:
                    logger.info(
                        f"Ignoring respawn request from {nickname} as the game is over"
                    )
                    response = {"type": "respawn_failed", "message": "Game is over"}
                    self.server_socket.sendto(
                        (json.dumps(response) + "\n").encode(), addr
                    )
                    return

                cooldown = room.game.get_train_cooldown(nickname)

                if cooldown > 0:
                    # Inform the client of the remaining cooldown
                    response = {"type": "death", "remaining": cooldown}
                    self.server_socket.sendto(
                        (json.dumps(response) + "\n").encode(), addr
                    )
                    return

                # Add the train to the game
                if room.game.add_train(nickname):
                    response = {"type": "spawn_success", "nickname": nickname}
                    self.server_socket.sendto(
                        (json.dumps(response) + "\n").encode(), addr
                    )
                else:
                    logger.warning(f"Failed to spawn train {nickname}")
                    # Inform the client of the failure
                    response = {
                        "type": "respawn_failed",
                        "message": "Failed to spawn train",
                    }
                    self.server_socket.sendto(
                        (json.dumps(response) + "\n").encode(), addr
                    )

            elif message.get("action") == "direction":
                if nickname in room.game.trains and room.game.contains_train(nickname):
                    room.game.trains[nickname].change_direction(message["direction"])

            elif message.get("action") == "drop_wagon":
                if nickname in room.game.trains and room.game.contains_train(nickname):
                    last_wagon_position = room.game.trains[nickname].drop_wagon()
                    if last_wagon_position:
                        # Create a new passenger at the position of the dropped wagon
                        new_passenger = Passenger(room.game)
                        new_passenger.position = last_wagon_position
                        new_passenger.value = 1
                        room.game.passengers.append(new_passenger)
                        room.game._dirty["passengers"] = True

                        # Notify the client of the success with the cooldown
                        response = {
                            "type": "drop_wagon_success",
                            "cooldown": BOOST_COOLDOWN_DURATION
                        }
                        self.server_socket.sendto(
                            (json.dumps(response) + "\n").encode(), addr
                        )
                    else:
                        # Calculate remaining cooldown time if the cooldown is active
                        message = "Cannot drop wagon (no wagons available)"
                        remaining_cooldown = 0
                        
                        if room.game.trains[nickname].boost_cooldown_active:
                            current_time = time.time()
                            elapsed_time = current_time - room.game.trains[nickname].start_cooldown_time
                            remaining_cooldown = max(0, BOOST_COOLDOWN_DURATION - elapsed_time)
                            message = f"Cannot drop wagon (cooldown active for {remaining_cooldown:.1f} more seconds)"
                        
                        # Notify the client that the drop_wagon action failed
                        response = {
                            "type": "drop_wagon_failed",
                            "message": message,
                        }
                        self.server_socket.sendto(
                            (json.dumps(response) + "\n").encode(), addr
                        )

        except Exception as e:
            logger.error(f"Error handling client message: {e}")

    def send_cooldown_notification(self, nickname, cooldown, death_reason):
        """Send a cooldown notification to a specific client"""
        for room in self.rooms.values():
            for addr, name in room.clients.items():
                if name == nickname:
                    try:
                        # Skip AI clients - they don't need network messages
                        if (
                            isinstance(addr, tuple)
                            and len(addr) == 2
                            and addr[0] == "AI"
                        ):
                            return

                        response = {"type": "death", "remaining": cooldown, "reason": death_reason}
                        self.server_socket.sendto(
                            (json.dumps(response) + "\n").encode(), addr
                        )
                        return
                    except Exception as e:
                        logger.error(
                            f"Error sending cooldown notification to {nickname}: {e}"
                        )
                        return

    def ping_clients(self):
        """Thread that sends ping messages to all clients and checks for timeouts"""
        while self.running:
            
            current_time = time.time()

            # PART 1: Check all clients for timeouts
            for addr, last_activity in list(self.client_last_activity.items()):
                # Skip clients that are already marked as disconnected
                if addr in self.disconnected_clients:
                    continue

                # Check if client has timed out
                if current_time - last_activity > self.config.client_timeout_seconds:
                    # Client has timed out, handle disconnection
                    self.handle_client_disconnection(addr, "timeout")

            # PART 2: Send pings to clients in rooms
            clients_to_ping = set()
            for room in self.rooms.values():
                for addr in room.clients.keys():
                    clients_to_ping.add(addr)

            # Send pings to all active clients in rooms
            for addr in clients_to_ping:
                # Skip clients that are already marked as disconnected
                if addr in self.disconnected_clients:
                    continue

                # Skip AI clients - they don't need network messages
                if isinstance(addr, tuple) and len(addr) == 2 and addr[0] == "AI":
                    continue

                # Send a ping message to the client
                ping_message = {"type": "ping"}
                try:
                    self.server_socket.sendto(
                        (json.dumps(ping_message) + "\n").encode(), addr
                    )
                    # Add the client to the ping responses dictionary with the current time
                    self.ping_responses[addr] = current_time
                except Exception as e:
                    logger.debug(f"Error sending ping to client {addr}: {e}")

            # Wait for responses (half the ping interval)
            time.sleep(self.ping_interval / 2)

            # PART 3: Check for clients that haven't responded to pings
            for addr, ping_time in list(self.ping_responses.items()):
                # If the ping was sent more than ping_interval ago and no response was received
                if current_time - ping_time > self.ping_interval:
                    # Skip clients that are already marked as disconnected
                    if addr in self.disconnected_clients:
                        del self.ping_responses[addr]
                        continue

                    # Client hasn't responded to ping, mark as disconnected
                    self.handle_client_disconnection(addr, "ping timeout")

            # Sleep for the remaining time of the ping interval
            time.sleep(self.ping_interval / 2)
            # except Exception as e:
            #     logger.error(f"Error in ping_clients: {e}")
            #     # Sleep on error to avoid high CPU usage
            #     time.sleep(self.ping_interval)

    def handle_client_disconnection(self, addr, reason="unknown"):
        """Handle client disconnection - centralized method to avoid code duplication"""
        logger.debug(f"Handling client disconnection for {addr} due to {reason}")
        # Check if client is already marked as disconnected
        if addr in self.disconnected_clients:
            # Already disconnected, no need to process again
            return

        # Mark client as disconnected
        self.disconnected_clients.add(addr)

        nickname = self.addr_to_name.get(addr, "Unknown client")
        sciper = self.addr_to_sciper.get(addr) # Get sciper BEFORE deleting it

        # Only log at INFO level if this is a known client
        if nickname != "Unknown client":
            logger.info(f"Client {nickname} disconnected due to {reason}: {addr}")

            # Find the room this client is in and create an AI to control their train
            for room in self.rooms.values():
                if addr in room.clients:
                    # Store the name before removing the client
                    original_nickname = room.clients[addr]
                    logger.info(f"Removing {original_nickname} from room {room.id}")

                    # Remove the client from the room's client list first
                    del room.clients[addr]

                    # Now, check if any human clients remain
                    human_clients_count = 0
                    for client_addr_check in room.clients.keys():
                        # Count only human clients (not AI clients)
                        if not (
                            isinstance(client_addr_check, tuple)
                            and len(client_addr_check) == 2
                            and client_addr_check[0] == "AI"
                        ):
                            human_clients_count += 1

                    if human_clients_count == 0:
                        # Last human left, close the room. No need to create AI.
                        logger.info(
                            f"Last human client {original_nickname} left room {room.id}, closing room"
                        )
                        # remove_room handles setting flags, stopping threads, and cleanup
                        self.remove_room(room.id)
                    else:
                        if room.game.trains:
                            # Other human players remain. Create an AI for the disconnecting player's train if it exists.
                            if original_nickname in room.game.trains:
                                room.replace_player_by_ai(
                                    train_nickname_to_replace=original_nickname
                                )

                    break  # Exit the room loop as we found and processed the client

        else:
            # Log at debug level for unknown clients to reduce spam
            logger.debug(f"Unknown client disconnected due to {reason}: {addr}")

        self.record_disconnection(sciper, reason)

        # Clean up sciper information
        if addr in self.addr_to_sciper:
            # sciper = self.addr_to_sciper[addr] # Moved up
            if sciper and sciper in self.sciper_to_addr:
                del self.sciper_to_addr[sciper]
            del self.addr_to_sciper[addr]

        # Clean up game mode information
        if addr in self.addr_to_game_mode:
            del self.addr_to_game_mode[addr]

        if addr in self.client_last_activity:
            del self.client_last_activity[addr]

        if addr in self.ping_responses:
            del self.ping_responses[addr]

    def record_disconnection(self, sciper, reason):
        # Record disconnection stats *after* getting sciper and *before* potential errors/returns
        if sciper:
            premature = (reason != "client quit") # Consider premature if not an explicit quit
            logger.info(f"Calling record_disconnection for sciper {sciper}, premature={premature} (reason='{reason}')")
            try:
                stats_manager.record_disconnection(sciper, premature=premature)
            except Exception as e:
                logger.error(f"Error calling stats_manager.record_disconnection for {sciper}: {e}")

    def remove_room(self, room_id):
        """Remove a room from the server"""
        try:
            if room_id in self.rooms:
                logger.info(f"Removing room {room_id}")
                room = self.rooms[room_id]

                # 1. Signal the game to stop (if it exists and is running)
                if hasattr(room, 'game') and room.game and room.game.running:
                    logger.debug(f"Signaling game in room {room_id} to stop.")
                    room.game.running = False

                # 2. Signal the room's threads to stop
                if room.running:
                    logger.debug(f"Signaling room {room_id} threads to stop.")
                    room.running = False

                # 3. Wait for the game thread to finish if it's running
                if room.game_thread and room.game_thread.is_alive():
                    logger.info(
                        f"Waiting for game thread in room {room_id} to terminate before removal"
                    )
                    room.game_thread.join(timeout=2.0)  # Wait a bit
                    if room.game_thread.is_alive():
                        logger.warning(
                            f"Game thread for room {room_id} did not terminate gracefully."
                        )

                # 4. Stop and clean up AI clients associated with this room
                ai_to_remove = []
                # Use list() to avoid modification during iteration if necessary, although it might not be strictly needed here
                for ai_name, ai_client in list(self.rooms[room_id].ai_clients.items()):
                    # Check if ai_client.room exists before accessing id
                    if ai_client.room and ai_client.room.id == room_id:
                        logger.debug(f"Stopping AI client {ai_name} in room {room_id}")
                        ai_client.stop()
                        ai_to_remove.append(ai_name)

                for ai_name in ai_to_remove:
                    if ai_name in self.rooms[room_id].ai_clients:
                        del self.rooms[room_id].ai_clients[ai_name]
                    if ai_name in self.rooms[room_id].used_ai_names:
                        # Use discard to avoid KeyError if name somehow already removed
                        self.rooms[room_id].used_ai_names.discard(ai_name)

                # 5. Now remove the room itself
                del self.rooms[room_id]
                logger.info(f"Room {room_id} removed successfully")
            else:
                logger.warning(f"Attempted to remove non-existent room {room_id}")
        except Exception as e:
            logger.error(f"Error removing room {room_id}: {e}")

    def run(self):
        """Main server loop"""

        def signal_handler(sig, frame):
            # Only set the running flag to false. Cleanup happens after the main loop.
            logger.info("Shutdown signal received. Initiating graceful shutdown...")
            self.running = False
            # Removed direct cleanup and sys.exit from here

        # Register signal handler for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("Server running. Press Ctrl+C to stop.")

        while self.running:
            # Main loop waits for running flag to become false
            try:
                # Use a timeout to allow checking self.running more frequently
                # and prevent blocking indefinitely if no other activity occurs.
                time.sleep(0.5)
            except InterruptedError:
                # Catch potential interruption if sleep is interrupted by signal
                continue  # Check self.running again

        # --- Shutdown sequence starts here, after the loop ---
        logger.info("Shutting down server...")

        # 1. Disconnect clients (must happen before closing the socket)
        client_addresses = list(self.addr_to_name.keys())  # Copy keys
        if client_addresses:
            logger.info(f"Disconnecting {len(client_addresses)} clients...")
            for addr in client_addresses:
                # try-except around send_disconnect in case socket is already bad
                try:
                    logger.debug(f"Disconnecting client {addr}")
                    self.send_disconnect(addr, "Server shutting down")
                    # Optional small delay to increase chance of message delivery
                    time.sleep(0.01)
                except Exception as e:
                    logger.error(f"Error sending disconnect to {addr}: {e}")
        else:
            logger.info("No clients connected to disconnect.")

        threads_to_join = []
        if hasattr(self, "threads"):  # Check if attribute exists
            threads_to_join.extend(self.threads)
        if (
            hasattr(self, "ping_thread") and self.ping_thread is not None
        ):  # Check ping_thread exists and is not None
            threads_to_join.append(self.ping_thread)
        # Add other relevant threads if they exist and need joining, e.g., accept_clients thread if stored.

        active_threads = [
            t for t in threads_to_join if t and t.is_alive()
        ]  # Check for None threads too

        if active_threads:
            logger.info(f"Waiting for {len(active_threads)} threads to finish...")
            for thread in active_threads:
                try:
                    thread.join(timeout=1.0)  # Use timeout
                    if thread.is_alive():
                        logger.warning(
                            f"Thread {thread.name} did not finish within timeout."
                        )
                except Exception as e:
                    logger.error(f"Error joining thread {thread.name}: {e}")
        else:
            logger.info("No active threads found to join.")

        logger.info("Server shutdown complete")
        # No sys.exit(0) here, allow the function to return naturally
