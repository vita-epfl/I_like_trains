from audioop import add
import socket
import json
import threading
import time
import sys
import logging
import uuid
import random
import os

from game import Game
from passenger import Passenger

try:
    from ai_client import AIClient
except ImportError:
    pass

# Transfer frequency
MAX_FREQUENCY = 30

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)

# Directions
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

# Default host
HOST = "localhost"
ALLOW_MULTIPLE_CONNECTIONS = True
DEFAULT_NB_PLAYERS_PER_ROOM = 0  # Default max players per room

# Scores file path
SCORES_FILE_PATH = "player_scores.json"

# List of names for AI-controlled clients
AI_NAMES = [
    "Bot Adrian", "Bot Albert", "Bot Allen", "Bot Andy", "Bot Arnold", "Bot Bert", "Bot Cecil", 
    "Bot Charles", "Bot Clarence", "Bot Elmer", "Bot Ernest", "Bot Felix", "Bot Frank", "Bot Fred", 
    "Bot Gilbert", "Bot Gus", "Bot Hank", "Bot Howard", "Bot James", "Bot Lester"
]

# Client timeout in seconds (how long to wait before considering a client disconnected)
CLIENT_TIMEOUT = 1.0
GAME_LIFE_TIME = 60*1  # 5 minutes

# Check if an IP address has argued in argument
if len(sys.argv) > 1:
    HOST = sys.argv[1]

# Check if max players per room is provided as second argument
if len(sys.argv) > 2:
    try:
        DEFAULT_NB_PLAYERS_PER_ROOM = int(sys.argv[2])
    except ValueError:
        print(f"Invalid number of players value: {sys.argv[2]}. Using default: {DEFAULT_NB_PLAYERS_PER_ROOM}")


def setup_server_logger():
    # Delete existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

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
    modules = ["server.game", "server.train", "server.passenger", "server.delivery_zone", "server.ai_client", "server.ai_agent"]
    for module in modules:
        logger = logging.getLogger(module)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.addHandler(console_handler)

    return server_logger


# Configure the server logger
logger = setup_server_logger()
logger.info(f"The server starts on {HOST}")


def load_best_scores():
    """Load player scores from file"""
    if os.path.exists(SCORES_FILE_PATH):
        try:
            with open(SCORES_FILE_PATH, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error decoding scores file. Creating a new one.")
            return {}
        except Exception as e:
            logger.error(f"Error loading scores file: {e}")
            return {}
    return {}


def save_scores(scores):
    """Save player scores to file"""
    try:
        with open(SCORES_FILE_PATH, 'w') as f:
            json.dump(scores, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving scores to file: {e}")


def update_best_score(player_name, player_sciper, score, scores_dict):
    """Update player's best score if the new score is higher"""
    # Use sciper as the unique identifier for scores
    if player_sciper in scores_dict:
        if score > scores_dict[player_sciper]:
            scores_dict[player_sciper] = score
            return True
    else:
        scores_dict[player_sciper] = score
        return True
    return False


def display_high_scores(scores, limit=10):
    """Display the current high scores"""
    if not scores:
        logger.info("No high scores available yet")
        return
        
    # Sort scores in descending order
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    logger.info("===== HIGH SCORES =====")
    for i, (player, score) in enumerate(sorted_scores[:limit], 1):
        logger.info(f"{i}. {player}: {score}")
    logger.info("======================")


class Room:
    def __init__(self, room_id, nb_players, running, server):
        self.id = room_id
        self.nb_players = nb_players
        self.game = Game(server.send_cooldown_notification, self.nb_players)
        self.game.room_id = room_id  # Store the room ID in the Game object
        self.game.server = server  # Give a reference to the server
        self.clients = {}  # {addr: agent_name}
        self.game_thread = None
        self.running = running  # The room is active by default
        self.waiting_room_thread = threading.Thread(target=self.broadcast_waiting_room)
        self.waiting_room_thread.daemon = True
        self.waiting_room_thread.start()
        self.game_start_time = None  # Track when the game starts
        self.game_over = False  # Track if the game is over
        logger.info(f"Room {room_id} created with number of players {nb_players}")

    def start_game(self):
        self.state_thread = threading.Thread(target=self.broadcast_game_state)
        self.state_thread.daemon = True
        self.state_thread.start()

        # Start the game timer thread
        self.game_timer_thread = threading.Thread(target=self.game_timer)
        self.game_timer_thread.daemon = True
        self.game_timer_thread.start()

        logger.info(f"\nStarting game for room {self.id}")
        if not self.game_thread:
            # Initialize game size based on connected players
            self.game.initialize_game_size(len(self.clients))

            # Start the game thread
            self.game_thread = threading.Thread(target=self.game.run)
            self.game_thread.daemon = True
            self.game_thread.start()

            # Record the game start time
            self.game_start_time = time.time()

            response = {"type": "game_started_success"}
            # Send response to all clients
            for client_addr in list(self.clients.keys()):
                try:
                    self.game.server.server_socket.sendto((json.dumps(response) + "\n").encode(), client_addr)
                except Exception as e:
                    logger.error(f"Error sending start success to client: {e}")

            logger.info(f"Game started in room {self.id} with {len(self.clients)} players")

    def game_timer(self):
        """Thread that monitors game time and ends the game after GAME_LIFE_TIME seconds"""
        while self.running and not self.game_over:
            if self.game_start_time is not None:
                elapsed_time = time.time() - self.game_start_time
                
                # If the game has been running for GAME_LIFE_TIME seconds, end it
                if elapsed_time >= GAME_LIFE_TIME:
                    self.end_game()
                    break
            
            time.sleep(1)  # Check every second

    def end_game(self):
        """End the game and send final scores to all clients"""
        if self.game_over:
            return  # Game already ended
            
        logger.info(f"Game in room {self.id} has ended after {GAME_LIFE_TIME} seconds")
        self.game_over = True
        
        # Collect final scores
        final_scores = []
        scores_dict = self.game.server.best_scores
        scores_updated = False
        
        for train_name, best_score in self.game.best_scores.items():
            logger.debug(f"Train {train_name} has best score {best_score}")
            
            # Find the client address associated with this train name
            client_addr = None
            for addr, name in self.clients.items():
                if name == train_name:
                    client_addr = addr
                    break
            
            # Get the sciper associated with this client address
            player_sciper = None
            if client_addr and client_addr in self.game.server.addr_to_sciper:
                player_sciper = self.game.server.addr_to_sciper[client_addr]
            
            final_scores.append({
                "name": train_name,
                "best_score": best_score
            })
            
            # Update best score in the scores file if we have a valid sciper
            if player_sciper:
                if update_best_score(train_name, player_sciper, best_score, scores_dict):
                    scores_updated = True
                    logger.info(f"Updated best score for {train_name} (sciper: {player_sciper}): {best_score}")
            
        # Save scores if any were updated
        if scores_updated:
            save_scores(scores_dict)
            
        # Sort scores in descending order
        final_scores.sort(key=lambda x: x["best_score"], reverse=True)

        # logger.debug(f"Final scores: {final_scores}")
        
        # Create game over message
        game_over_data = {
            "type": "game_over",
            "data": {
                "message": "Game is over. Time limit reached.",
                "final_scores": final_scores,
                "duration": GAME_LIFE_TIME,
                "best_scores": scores_dict
            }
        }
        
        # Send to all clients
        state_json = json.dumps(game_over_data) + "\n"
        for client_addr in list(self.clients.keys()):
            try:
                self.game.server.server_socket.sendto(state_json.encode(), client_addr)
            except Exception as e:
                logger.error(f"Error sending game over data to client: {e}")
                
        # Stop the game
        self.game.running = False
        
        # Close the room after a short delay to ensure all clients receive the game over message
        def close_room_after_delay():
            time.sleep(2)  # Wait 2 seconds to ensure clients receive the game over message
            logger.info(f"Closing room {self.id} after game over")
            self.running = False
            # Remove the room from the server
            if hasattr(self.game, 'server') and self.game.server:
                self.game.server.remove_room(self.id)
        
        # Start a thread to close the room after a delay
        close_thread = threading.Thread(target=close_room_after_delay)
        close_thread.daemon = True
        close_thread.start()

    def is_full(self):
        # logger.debug(f"Room {self.id} has {len(self.clients)} clients and {self.nb_players} max players")
        return len(self.clients) >= self.nb_players

    def get_player_count(self):
        return len(self.clients)

    def broadcast_waiting_room(self):
        """Broadcast waiting room data to all clients"""
        last_update = time.time()
        while self.running:
            try:
                if self.clients and not self.game_thread:
                    current_time = time.time()
                    if current_time - last_update >= 1.0 / MAX_FREQUENCY:  # Limit to MAX_FREQUENCY Hz
                        if self.clients:
                            waiting_room_data = {
                                "type": "waiting_room",
                                "data": {
                                    "room_id": self.id,
                                    "players": list(self.clients.values()),
                                    "nb_players": self.nb_players,
                                    "game_started": self.game_thread is not None
                                }
                            }

                            state_json = json.dumps(waiting_room_data) + "\n"
                            for client_addr in list(self.clients.keys()):
                                try:
                                    self.game.server.server_socket.sendto(state_json.encode(), client_addr)
                                except Exception as e:
                                    logger.error(f"Error sending waiting room data to client: {e}")

                        last_update = current_time

                time.sleep(1.0 / (MAX_FREQUENCY * 2))  # Sleep for half the period
            except Exception as e:
                logger.error(f"Error in broadcast_waiting_room: {e}")
                time.sleep(1.0 / MAX_FREQUENCY)

    def broadcast_game_state(self):
        """Thread that periodically sends the game state to clients"""
        self.running = True
        logger.info(f"Starting broadcast thread for room {self.id}")
        
        # Send initial state to all clients
        initial_state = {
            "type": "initial_state",
            "data": {
                "game_life_time": GAME_LIFE_TIME,  # Send total game time to clients
                "start_time": time.time()  # Send server start time for synchronization
            }
        }
        
        initial_state_json = json.dumps(initial_state) + "\n"
        for client_addr in list(self.clients.keys()):
            try:
                self.game.server.server_socket.sendto(initial_state_json.encode(), client_addr)
            except Exception as e:
                logger.error(f"Error sending initial state to client: {e}")
        
        last_update = time.time()
        while self.running:
            try:
                # Calculate the time elapsed since the last update
                current_time = time.time()
                elapsed = current_time - last_update

                # If enough time has passed
                if elapsed >= 1.0 / MAX_FREQUENCY:
                    # Get the game state with only the modified data
                    state = self.game.get_state()
                    if state:  # If data has been modified
                        # Create the data packet
                        state_data = {
                            "type": "state",
                            "data": state
                        }

                        # Send the state to all clients
                        state_json = json.dumps(state_data) + "\n"
                        for client_addr in list(self.clients.keys()):
                            try:
                                self.game.server.server_socket.sendto(state_json.encode(), client_addr)
                            except Exception as e:
                                logger.error(f"Error sending state to client: {e}")

                    last_update = current_time

                # Wait a bit to avoid overloading the CPU
                time.sleep(1.0 / (MAX_FREQUENCY * 2))
            except Exception as e:
                logger.error(f"Error in broadcast_game_state: {e}")
                time.sleep(1.0 / MAX_FREQUENCY)


class Server:
    def __init__(self):
        self.rooms = {}  # {room_id: Room}
        self.lock = threading.Lock()
        
        # Load player scores from file
        self.best_scores = load_best_scores()
        # logger.info(f"Loaded {len(self.scores)} player scores from file")
        
        # Display high scores
        display_high_scores(self.best_scores)
        
        # Create UDP socket with proper error handling
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((HOST, 5555))
            logger.info(f"UDP socket created and bound to {HOST}:5555")
        except Exception as e:
            logger.error(f"Error creating UDP socket: {e}")
            raise
            
        self.running = True
        self.nb_players = DEFAULT_NB_PLAYERS_PER_ROOM
        self.addr_to_name = {}  # Maps client addresses to agent names
        self.addr_to_sciper = {}  # Maps client addresses to scipers
        self.sciper_to_addr = {}  # Maps scipers to client addresses
        self.client_last_activity = {}  # Maps client addresses to last activity timestamp
        self.disconnected_clients = set()  # Track disconnected clients by full address tuple (IP, port)
        self.ai_clients = {}  # Maps train names to AI clients
        self.used_ai_names = set()  # Track AI names that are already in use
        
        # Client activity tracking for disconnection detection
        self.client_timeout = CLIENT_TIMEOUT  # Consider client disconnected after 2 seconds of inactivity
        
        # Ping tracking for active connection checking
        self.ping_interval = self.client_timeout/2  # Send pings every 1 second
        self.ping_responses = {}  # Track which clients have responded to pings
        
        # Start the ping thread (handles all client timeouts)
        self.ping_thread = threading.Thread(target=self.ping_clients)
        self.ping_thread.daemon = True
        self.ping_thread.start()
        
        # Get the number of players per room
        while True:
            try:
                player_input = input("Enter number of players per room: ").strip()
                if not player_input:
                    print("Please enter a valid number (minimum 1)")
                    continue
                self.nb_players = int(player_input)
                if self.nb_players < 1:
                    print("Number of players must be at least 1")
                    continue
                break
            except ValueError:
                print("Please enter a valid number (minimum 1)")

        # Create the first room
        self.create_room(self.nb_players, True)

        # Start accepting clients
        threading.Thread(target=self.accept_clients).start()
        logger.info(f"Server started on {HOST}")

    def create_room(self, nb_players, running):
        """Create a new room with specified number of players"""
        room_id = str(uuid.uuid4())[:8]
        new_room = Room(room_id, nb_players, running, server=self)
        logger.info(f"Created new room {room_id} with {nb_players} players")
        self.rooms[room_id] = new_room
        return new_room

    def get_available_room(self, nb_players):
        """Get an available room or create a new one if needed"""
        # logger.debug(f"Getting available room for {nb_players} players")
        # First try to find a non-full room
        for room in self.rooms.values():
            # logger.debug(f"Checking room {room.id} for {nb_players} players")
            if (room.nb_players == nb_players and 
                not room.is_full() and 
                not room.game_thread):
                return room
        logger.debug(f"No suitable room found for {nb_players} players")
        # If no suitable room found, create a new one
        return self.create_room(nb_players, True)

    def accept_clients(self):
        """Thread that waits for new connections"""
        logger.info("Server is listening for UDP packets")
        error_count = {}  # Track error count per client
        error_threshold = 3  # Number of consecutive errors before considering a client disconnected
        
        while self.running:
            try:
                # Receive data from any client
                data, addr = self.server_socket.recvfrom(1024)
                
                # If we successfully received data from this client, reset their error count
                if addr in error_count:
                    error_count[addr] = 0
                
                if not data:
                    continue
                    
                data_str = data.decode()
                # logger.debug(f"Received UDP data from {addr}: {data_str[:50]}...")
                
                # Process the incoming message
                if data_str:
                    # Handle multiple messages in one packet
                    messages = data_str.split("\n")
                    for message_str in messages:
                        if not message_str:
                            continue
                        
                        try:
                            message = json.loads(message_str)
                            # Process the message
                            self.process_message(message, addr)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON received from {addr}: {message_str}")
                        except Exception as e:
                            logger.error(f"Error processing message from {addr}: {e}")
            except socket.error as e:
                # For UDP, we don't know which client caused the error
                # So we only log the error and don't mark any client as disconnected
                if "[WinError 10054]" in str(e):
                    # This is a connection reset error, which is expected in UDP
                    # We'll just log it at a lower level or not at all
                    pass  # Don't log connection reset errors at all
                else:
                    logger.error(f"Socket error: {e}")
                time.sleep(0.1)  # Add a small delay to avoid high CPU usage on error
            except Exception as e:
                logger.error(f"Error in accept_clients: {e}")
                time.sleep(0.1)  # Add a small delay to avoid high CPU usage on error

    def process_message(self, message, addr):
        """Process incoming messages from clients"""

        if "action" in message and message["action"] not in ["check_name", "check_sciper"]:
            # Update client activity timestamp
            self.client_last_activity[addr] = time.time()
        
        # Handle ping responses
        if "type" in message and message["type"] == "pong":
            self.client_last_activity[addr] = time.time()
            # Client has responded to a ping, update the ping responses dictionary
            if addr in self.ping_responses:
                del self.ping_responses[addr]  # Remove from pending responses
            return
        
        # If this client was previously marked as disconnected
        if addr in self.disconnected_clients:
            # Allow check_name and check_sciper actions even if client was previously disconnected
            if "action" in message and message["action"] in ["check_name", "check_sciper"]:
                # Process these actions normally
                pass
            elif "agent_name" not in message or "agent_sciper" not in message:
                # Don't log a warning for every message, just silently ignore it
                return
        
        # For name check requests
        if "action" in message and message["action"] == "check_name":
            self.handle_name_check(message, addr)
            return

        # For sciper check requests
        if "action" in message and message["action"] == "check_sciper":
            self.handle_sciper_check(message, addr)
            return
            
        # For high scores request
        if "type" in message and message["type"] == "high_scores":
            self.handle_high_scores_request(addr)
            return
            
        # For agent name initialization
        if "type" in message and message["type"] == "agent_ids" and "agent_name" in message and "agent_sciper" in message and addr not in self.addr_to_name:
            # use handle_name_check and handle_sciper_check to check if the name and sciper are available
            logger.debug(f"Checking name and sciper availability for {message['agent_name']} ({message['agent_sciper']})")
            if self.handle_name_check(message, None) and self.handle_sciper_check(message, None):
                self.handle_new_client(message, addr)
            else:
                # ask the client to disconnect
                self.send_disconnect(addr)
                logger.warning(f"Name or sciper not available for {addr}")
            return

        # For all other messages, find the client's room and handle the message
        agent_sciper = self.addr_to_sciper.get(addr)

        if agent_sciper:
            # Find which room this client belongs to
            client_room = None
            for room in self.rooms.values():
                if addr in room.clients:
                    client_room = room
                    break
                    
            if client_room:
                self.handle_client_message(addr, message, client_room)
            else:
                logger.warning(f"Received message from {addr} ({agent_sciper}) but client not in any room")
        else:
            # Check if this is a message from a client that was in a recently closed room
            # Only log at debug level if it's not a common message type
            if "type" in message and message["type"] in ["pong", "high_scores"]:
                # These are common messages, don't log them to reduce spam
                pass
            elif "action" in message and message["action"] in ["check_name"]:
                # Handle common action messages without logging
                pass
            elif "action" in message and message["action"] in ["check_sciper"]:
                # Handle common action messages without logging
                pass
            else:
                logger.debug(f"Received message from unknown client {addr}: {message}")
                # ask the client to disconnect
                self.send_disconnect(addr)

    def send_disconnect(self, addr):
        """Disconnect a client from the server"""
        # ask the client to disconnect
        disconnect_message = {
            "type": "disconnect",
            "reason": "Unknown client or invalid message format"
        }
        try:
            self.server_socket.sendto((json.dumps(disconnect_message) + "\n").encode(), addr)
            logger.info(f"Sent disconnect request to unknown client {addr}")
        except Exception as e:
            logger.error(f"Error sending disconnect request to {addr}: {e}")


    def handle_high_scores_request(self, addr):
        """Handle a request for high scores"""
        # Sort scores in descending order
        sorted_scores = sorted(self.best_scores.items(), key=lambda x: x[1], reverse=True)
        top_scores = sorted_scores[:10]  # Get top 10 scores
        
        # Create response
        response = {
            "type": "high_scores",
            "scores": [{"name": player, "score": score} for player, score in top_scores]
        }
        
        try:
            self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
            logger.info(f"Sent high scores to client at {addr}")
        except Exception as e:
            logger.error(f"Error sending high scores: {e}")
    
    def handle_name_check(self, message, addr):
        """Handle name check requests"""
        # Update client activity timestamp
        # self.client_last_activity[addr] = time.time()
        # logger.debug(f"Checking name availability for {message['agent_name']}")
        
        name_to_check = message.get("agent_name", "")
        if addr:
            if not name_to_check or len(name_to_check) == 0:
                # Empty name, considered as not available
                response = {
                    "type": "name_check",
                    "available": False
                }
            
                try:
                    self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
                except Exception as e:
                    logger.error(f"Error sending name check response: {e}")
                logger.debug(f"Name check for '{name_to_check}': not available")
                return False

        # Check if the name exists in any room
        name_available = True
        for room_id, room in self.rooms.items():
            if name_to_check in room.clients.values():
                name_available = False
                logger.debug(f"Name '{name_to_check}' found in room {room_id}")
                break

        # Check if name not in the ai names
        if name_to_check in AI_NAMES:
            name_available = False

        if addr:
            # Prepare the response with best score if available
            response = {
                "type": "name_check",
                "available": name_available
            }

            try:
                self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
                logger.info(f"Name check for '{name_to_check}': {'available' if name_available else 'not available'}")
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
        if not sciper_to_check or len(sciper_to_check) == 0 or not sciper_to_check.isdigit():
            if addr:
                # Empty sciper, considered as not available
                response = {
                    "type": "sciper_check",
                    "available": False
                }
                try:
                    self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
                except Exception as e:
                    logger.error(f"Error sending sciper check response: {e}")
                logger.debug(f"Sciper check for '{sciper_to_check}': not available")
                return False

        # Check if the sciper exists in our mapping
        sciper_available = sciper_to_check not in self.sciper_to_addr

        if addr:
            # Prepare the response with best score if available
            response = {
                "type": "sciper_check",
                "available": sciper_available
            }
        
            # Include best score if the player has played before
            if sciper_to_check in self.best_scores:
                response["best_score"] = self.best_scores[sciper_to_check]
                logger.info(f"Player with sciper '{sciper_to_check}' has a best score of {self.best_scores[sciper_to_check]}")
        
            try:
                self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
                logger.info(f"Sciper check for '{sciper_to_check}': {'available' if sciper_available else 'not available'}")
            except Exception as e:
                logger.error(f"Error sending sciper check response: {e}")

        return sciper_available

    def handle_new_client(self, message, addr):
        """Handle new client connection"""
        
        agent_name = message.get("agent_name", "")
        agent_sciper = message.get("agent_sciper", "")
        if not agent_name:
            logger.warning("No agent name provided")
            return

        if not agent_sciper:
            logger.warning("No agent sciper provided")
            return

        # Initialize client activity tracking
        self.client_last_activity[addr] = time.time()

        # Check if this address is already associated with a different name or sciper
        if addr in self.addr_to_name and self.addr_to_name[addr] != agent_name:
            old_name = self.addr_to_name[addr]
            logger.info(f"Client at {addr} changed name from {old_name} to {agent_name}")
            
            # Update the name in any rooms where this client exists
            for room in self.rooms.values():
                if addr in room.clients:
                    room.clients[addr] = agent_name
                    break

        # Log new client connection
        logger.info(f"New client {agent_name} (sciper: {agent_sciper}) connecting from {addr}")

        # Associate address with name and sciper
        self.addr_to_name[addr] = agent_name
        self.addr_to_sciper[addr] = agent_sciper
        self.sciper_to_addr[agent_sciper] = addr
        
        # Assign to a room
        selected_room = self.get_available_room(self.nb_players)
        selected_room.clients[addr] = agent_name
        logger.info(f"Agent {agent_name} (sciper: {agent_sciper}) joined room {selected_room.id}")
        
        # Send join success response immediately
        response = {
            "type": "join_success",
            "data": {
                "room_id": selected_room.id,
                "current_players": len(selected_room.clients),
                "max_players": selected_room.nb_players
            }
        }
        self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
        logger.debug(f"Sent join success response to {agent_name}")

        # Send initial game state immediately
        logger.debug(f"Sending initial game state to {agent_name}")
        game_status = {
            "type": "waiting_room",
            "data": {
                "room_id": selected_room.id,
                "players": list(selected_room.clients.values()),
                "nb_players": selected_room.nb_players,
                "game_started": selected_room.game_thread is not None
            }
        }
        self.server_socket.sendto((json.dumps(game_status) + "\n").encode(), addr)

        # If room is now full, start the game automatically
        if selected_room.is_full():
            selected_room.start_game()

    def handle_client_message(self, addr, message, room):
        """Handles messages received from the client"""
        try:
            # Update client activity timestamp
            
            
            agent_name = room.clients.get(addr)

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
                    logger.info(f"Ignoring respawn request from {agent_name} as the game is over")
                    response = {"type": "respawn_failed", "message": "Game is over"}
                    self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
                    return
                
                cooldown = room.game.get_train_cooldown(agent_name)
                
                if cooldown > 0:
                    # Inform the client of the remaining cooldown
                    response = {"type": "death", "remaining": cooldown}
                    self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
                    return
                
                # Add the train to the game
                if room.game.add_train(agent_name):
                    response = {"type": "spawn_success", "agent_name": agent_name}
                    self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
                else:
                    logger.warning(f"Failed to spawn train {agent_name}")
                    # Inform the client of the failure
                    response = {"type": "respawn_failed", "message": "Failed to spawn train"}
                    self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)

            elif message.get("action") == "direction":
                if agent_name in room.game.trains and room.game.is_train_alive(agent_name):
                    # logger.debug(f"Received direction change request from {agent_name} {message['direction']}")
                    room.game.trains[agent_name].change_direction(message["direction"])
                # else:
                #     logger.warning(f"Failed to change direction for train {agent_name}")

            elif message.get("action") == "drop_wagon":
                if agent_name in room.game.trains and room.game.is_train_alive(agent_name):
                    # logger.debug(f"Received drop wagon request from {agent_name}")
                    last_wagon_position = room.game.trains[agent_name].drop_wagon()
                    if last_wagon_position:
                        # Create a new passenger at the position of the dropped wagon
                        new_passenger = Passenger(room.game)
                        new_passenger.position = last_wagon_position
                        new_passenger.value = 1
                        room.game.passengers.append(new_passenger)
                        room.game._dirty["passengers"] = True

                        # Send a confirmation to the client
                        response = {"type": "drop_wagon_success", "agent_name": agent_name, "position": last_wagon_position}
                        self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
                    else:
                        response = {"type": "drop_wagon_failed", "message": "Failed to drop wagon"}
                        self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)

            elif message.get("action") == "start_game":
                # logger.info(f"Received start game request from {agent_name}")
                # Check if the game is already started
                if not room.game_thread or not room.game_thread.is_alive():
                    # If the game is not yet started and there are enough players, start it
                    if room.get_player_count() >= self.nb_players:  # Require at least 2 players
                        logger.info(f"Starting game as number of players: {room.get_player_count()} and number of players: {self.nb_players}")
                        room.start_game()
                        logger.info(f"Game started by {agent_name}")
                    else:
                        return
        except Exception as e:
            logger.error(f"Error handling client message: {e}")

    def send_cooldown_notification(self, agent_name, cooldown):
        """Send a cooldown notification to a specific client"""
        for room in self.rooms.values():
            for addr, name in room.clients.items():
                if name == agent_name:
                    try:
                        response = {"type": "death", "remaining": cooldown}
                        self.server_socket.sendto((json.dumps(response) + "\n").encode(), addr)
                        # logger.debug(f"Sent cooldown notification to {agent_name}: {cooldown}s")
                        return  # Once we have found and notified the client, we can exit
                    except Exception as e:
                        logger.error(f"Error sending cooldown notification to {agent_name}: {e}")
                        return

    def remove_room(self, room_id):
        """Remove a room from the server"""
        with self.lock:
            if room_id in self.rooms:
                room = self.rooms[room_id]
                room.running = False
                
                # Stop the game
                if room.game:
                    room.game.running = False
                
                # Wait for game thread to terminate if it exists
                if room.game_thread and room.game_thread.is_alive():
                    logger.info(f"Waiting for game thread in room {room_id} to terminate")
                    room.game_thread.join(timeout=2.0)  # Wait up to 2 seconds
                
                # Note: We don't need to explicitly join waiting_room_thread and state_thread
                # as they are daemon threads and will be terminated when the program exits
                # They also check the room.running flag in their loops
                
                # Clear references to client sockets to help garbage collection
                for addr in list(room.clients.keys()):
                    if addr in self.addr_to_name:
                        agent_name = self.addr_to_name[addr]
                        logger.info(f"Removing client {agent_name} from room {room_id}")
                        del self.addr_to_name[addr]
                    if addr in self.addr_to_sciper:
                        agent_sciper = self.addr_to_sciper[addr]
                        del self.addr_to_sciper[addr]
                    if agent_sciper in self.sciper_to_addr:
                        del self.sciper_to_addr[agent_sciper]
                room.clients.clear()
                
                # Remove the room
                del self.rooms[room_id]
                logger.info(f"Room {room_id} removed")
                
                # If there are no more rooms, create a new one
                if not self.rooms:
                    logger.info("No more rooms, creating a new one")
                    self.create_room(self.nb_players, True)

    def ping_clients(self):
        """Thread that sends ping messages to all clients and checks for timeouts"""
        while self.running:
            try:
                current_time = time.time()
                
                # PART 1: Check all clients for timeouts
                for addr, last_activity in list(self.client_last_activity.items()):
                    # Skip clients that are already marked as disconnected
                    if addr in self.disconnected_clients:
                        continue
                        
                    # Check if client has timed out
                    if current_time - last_activity > self.client_timeout:
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
                        
                    # Send a ping message to the client
                    ping_message = {"type": "ping"}
                    try:
                        self.server_socket.sendto((json.dumps(ping_message) + "\n").encode(), addr)
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
            except Exception as e:
                logger.error(f"Error in ping_clients: {e}")
                time.sleep(self.ping_interval)  # Sleep on error to avoid high CPU usage
    
    def handle_client_disconnection(self, addr, reason="unknown"):
        """Handle client disconnection - centralized method to avoid code duplication"""
        agent_name = self.addr_to_name.get(addr, "Unknown client")
        agent_sciper = self.addr_to_sciper.get(addr, "Unknown client")

        # Only log at INFO level if this is a known client
        if agent_name != "Unknown client":
            logger.info(f"Client {agent_name} disconnected due to {reason}: {addr}")
        
            # Find the room this client is in and create an AI to control their train
            for room in self.rooms.values():
                if addr in room.clients:
                    # Remove client from room
                    logger.info(f"Removing {agent_name} from room {room.id}")

                    # Create an AI to control the train if it exists in the game
                    if agent_name in room.game.trains:
                        logger.info(f"Creating AI client for train {agent_name}")
                        self.create_ai_for_train(room, agent_name)
                    else:
                        logger.info(f"Didn't create AI client for train {agent_name} because agent_name in room game.trains is {room.game.trains[agent_name]}")
                    
                    # Remove client from room
                    del room.clients[addr]
                    
                    # Check if this was the last human client in the room
                    if len(room.clients) == 0:
                        logger.info(f"Last client left room {room.id}, closing room")
                        room.running = False
                        # Stop all AI clients in this room
                        for ai_name, ai_client in list(self.ai_clients.items()):
                            if ai_client.room.id == room.id:
                                ai_client.stop()
                                del self.ai_clients[ai_name]
                        # Remove the room
                        self.remove_room(room.id)
                    
                    break
        else:
            # Log at debug level for unknown clients to reduce spam
            logger.debug(f"Unknown client disconnected due to {reason}: {addr}")
        
        # Remove from activity tracking and add to disconnected clients
        if addr in self.client_last_activity:
            del self.client_last_activity[addr]
        if addr in self.addr_to_name:
            del self.addr_to_name[addr]
        if addr in self.addr_to_sciper:
            del self.addr_to_sciper[addr]
        if agent_sciper in self.sciper_to_addr:
            del self.sciper_to_addr[agent_sciper]
        if addr in self.ping_responses:
            del self.ping_responses[addr]
        self.disconnected_clients.add(addr)

    def create_ai_for_train(self, room, train_name):
        """Create an AI client to control a train after a player disconnects"""
        # Check if there's already an AI controlling this train
        if train_name in self.ai_clients:
            logger.warning(f"AI already exists for train {train_name}")
            return
            
        # Choose an AI name that's not already in use
        available_names = [name for name in AI_NAMES if name not in self.used_ai_names]
        if not available_names:
            # If all names are used, generate a random name
            ai_name = f"AI_{uuid.uuid4().hex[:6]}"
        else:
            ai_name = random.choice(available_names)
            
        self.used_ai_names.add(ai_name)
        
        # Change the train's name in the game
        if train_name in room.game.trains:
            # Save the train's color
            if train_name in room.game.train_colors:
                train_color = room.game.train_colors[train_name]
                room.game.train_colors[ai_name] = train_color
                del room.game.train_colors[train_name]
            
            # Get the train object
            train = room.game.trains[train_name]
            
            # Update the train's name
            train.agent_name = ai_name
            
            # Move the train to the new key in the dictionary
            room.game.trains[ai_name] = train
            del room.game.trains[train_name]
            logger.debug(f"Moved train {train_name} to {ai_name} in game")

            # # Mark trains as dirty to update clients
            # room.game._dirty["trains"] = True
            
            # Notify clients about the train rename
            state_data = {
                "type": "state",
                "data": {
                    "rename_train": [train_name, ai_name]
                }
            }
            
            # Send the rename notification to all clients in the room
            state_json = json.dumps(state_data) + "\n"
            for client_addr in list(room.clients.keys()):
                try:
                    self.server_socket.sendto(state_json.encode(), client_addr)
                except Exception as e:
                    logger.error(f"Error sending train rename notification to client: {e}")
            
            # Create the AI client with the new name
            self.ai_clients[ai_name] = AIClient(room, ai_name)

            # Add the ai_client to the game
            room.game.ai_clients[ai_name] = self.ai_clients[ai_name]
            
            # logger.info(f"Created AI client {ai_name} to control train previously owned by {train_name}")
        else:
            logger.warning(f"Train {train_name} not found in game, cannot create AI client")

    def run_game(self):
        """Main game loop"""
        while self.running:
            time.sleep(1)


if __name__ == "__main__":
    server = Server()
    # Main server loop
    server.run_game()
