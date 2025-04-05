from server.game import Game
import threading
import time
import json
import logging
import os

# Configure logger
logger = logging.getLogger("server.room")

# Game duration in seconds
GAME_LIFE_TIME = 60 * 5

# Waiting time before adding bots (in seconds)
WAITING_TIME_BEFORE_BOTS = 30  # 30 seconds

# Scores file path
SCORES_FILE_PATH = "player_scores.json"

# Transfer tick rate
TICK_RATE = 30


def update_best_score(player_sciper, score, scores_dict):
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


def save_scores(scores):
    """Save player scores to file"""
    try:
        with open(SCORES_FILE_PATH, "w") as f:
            json.dump(scores, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving scores to file: {e}")


def load_best_scores():
    """Load player scores from file"""
    if os.path.exists(SCORES_FILE_PATH):
        try:
            with open(SCORES_FILE_PATH, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Error decoding scores file. Creating a new one.")
            return {}
        except Exception as e:
            logger.error(f"Error loading scores file: {e}")
            return {}
    return {}


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
        self.room_creation_time = time.time()  # Track when the room was created
        self.first_client_join_time = None  # Track when the first client joins
        self.has_human_players = (
            False  # Track if the room has at least one human player
        )
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
                    # Skip AI clients - they don't need network messages
                    if (
                        isinstance(client_addr, tuple)
                        and len(client_addr) == 2
                        and client_addr[0] == "AI"
                    ):
                        continue
                    self.game.server.server_socket.sendto(
                        (json.dumps(response) + "\n").encode(), client_addr
                    )
                except Exception as e:
                    logger.error(f"Error sending start success to client: {e}")

            logger.info(
                f"Game started in room {self.id} with {len(self.clients)} players"
            )

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

            final_scores.append({"name": train_name, "best_score": best_score})

            # Update best score in the scores file if we have a valid sciper
            if player_sciper:
                if update_best_score(player_sciper, best_score, scores_dict):
                    scores_updated = True
                    logger.info(
                        f"Updated best score for {train_name} (sciper: {player_sciper}): {best_score}"
                    )

        # Save scores if any were updated
        if scores_updated:
            save_scores(scores_dict)

        # Sort scores in descending order
        final_scores.sort(key=lambda x: x["best_score"], reverse=True)

        # Create game over message
        game_over_data = {
            "type": "game_over",
            "data": {
                "message": "Game is over. Time limit reached.",
                "final_scores": final_scores,
                "duration": GAME_LIFE_TIME,
                "best_scores": scores_dict,
            },
        }

        # Send to all clients
        state_json = json.dumps(game_over_data) + "\n"
        for client_addr in list(self.clients.keys()):
            try:
                # Skip AI clients - they don't need network messages
                if (
                    isinstance(client_addr, tuple)
                    and len(client_addr) == 2
                    and client_addr[0] == "AI"
                ):
                    continue

                self.game.server.server_socket.sendto(state_json.encode(), client_addr)
            except Exception as e:
                logger.error(f"Error sending game over data to client: {e}")

        self.game.running = False

        # Close the room after a short delay to ensure all clients receive the game over message
        def close_room_after_delay():
            time.sleep(
                2
            )  # Wait 2 seconds to ensure clients receive the game over message
            logger.info(f"Closing room {self.id} after game over")
            self.running = False
            # Remove the room from the server
            if self.game.server:
                self.game.server.remove_room(self.id)

        # Start a thread to close the room after a delay
        close_thread = threading.Thread(target=close_room_after_delay)
        close_thread.daemon = True
        close_thread.start()

    def is_full(self):
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
                    if (
                        current_time - last_update >= 1.0 / TICK_RATE
                    ):  # Limit to TICK_RATE Hz
                        if self.clients:
                            # Calculate remaining time before adding bots
                            remaining_time = 0
                            if self.has_human_players:
                                # Use the time the first client joined if available, otherwise creation time
                                start_time = (
                                    self.first_client_join_time
                                    if self.first_client_join_time is not None
                                    else self.room_creation_time
                                )
                                elapsed_time = current_time - start_time
                                remaining_time = max(
                                    0, WAITING_TIME_BEFORE_BOTS - elapsed_time
                                )

                                # If time is up and room is not full, add bots and start the game
                                if (
                                    remaining_time == 0
                                    and not self.is_full()
                                    and not self.game_thread
                                ):
                                    logger.info(
                                        f"Waiting time expired for room {self.id}, adding bots and starting game"
                                    )
                                    self.fill_with_bots()

                            waiting_room_data = {
                                "type": "waiting_room",
                                "data": {
                                    "room_id": self.id,
                                    "players": list(self.clients.values()),
                                    "nb_players": self.nb_players,
                                    "game_started": self.game_thread is not None,
                                    "waiting_time": int(remaining_time),
                                },
                            }

                            state_json = json.dumps(waiting_room_data) + "\n"
                            for client_addr in list(self.clients.keys()):
                                try:
                                    # Skip AI clients - they don't need network messages
                                    if (
                                        isinstance(client_addr, tuple)
                                        and len(client_addr) == 2
                                        and client_addr[0] == "AI"
                                    ):
                                        continue

                                    self.game.server.server_socket.sendto(
                                        state_json.encode(), client_addr
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Error sending waiting room data to client: {e}"
                                    )

                        last_update = current_time

                # Sleep for half the period
                time.sleep(1.0 / (TICK_RATE * 2))
            except Exception as e:
                logger.error(f"Error in broadcast_waiting_room: {e}")
                time.sleep(1.0 / TICK_RATE)

    def broadcast_game_state(self):
        """Thread that periodically sends the game state to clients"""
        self.running = True
        logger.info(f"Starting broadcast thread for room {self.id}")

        # Send initial state to all clients
        initial_state = {
            "type": "initial_state",
            "data": {
                "game_life_time": GAME_LIFE_TIME,  # Send total game time to clients
                "start_time": time.time(),  # Send server start time for synchronization
            },
        }

        initial_state_json = json.dumps(initial_state) + "\n"
        for client_addr in list(self.clients.keys()):
            try:
                # Skip AI clients - they don't need network messages
                if (
                    isinstance(client_addr, tuple)
                    and len(client_addr) == 2
                    and client_addr[0] == "AI"
                ):
                    continue
                self.game.server.server_socket.sendto(
                    initial_state_json.encode(), client_addr
                )
            except Exception as e:
                logger.error(f"Error sending initial state to client: {e}")

        last_update = time.time()
        while self.running:
            try:
                # Calculate the time elapsed since the last update
                current_time = time.time()
                elapsed = current_time - last_update

                # If enough time has passed
                if elapsed >= 1.0 / TICK_RATE:
                    # Get the game state with only the modified data
                    state = self.game.get_state()
                    if state:  # If data has been modified
                        # Create the data packet
                        state_data = {"type": "state", "data": state}

                        # Send the state to all clients
                        state_json = json.dumps(state_data) + "\n"
                        for client_addr in list(self.clients.keys()):
                            try:
                                # Skip AI clients - they don't need network messages
                                if (
                                    isinstance(client_addr, tuple)
                                    and len(client_addr) == 2
                                    and client_addr[0] == "AI"
                                ):
                                    continue

                                self.game.server.server_socket.sendto(
                                    state_json.encode(), client_addr
                                )
                            except Exception as e:
                                logger.error(f"Error sending state to client: {e}")

                    last_update = current_time

                # Wait a bit to avoid overloading the CPU
                time.sleep(1.0 / (TICK_RATE * 2))
            except Exception as e:
                logger.error(f"Error in broadcast_game_state: {e}")
                time.sleep(1.0 / TICK_RATE)

    def fill_with_bots(self):
        """Fill the room with bots and start the game"""
        server = self.game.server
        current_players = len(self.clients)
        bots_needed = self.nb_players - current_players

        if bots_needed <= 0:
            return

        logger.info(f"Adding {bots_needed} bots to room {self.id}")

        # Add bots to the room
        for _ in range(bots_needed):
            server.create_ai_for_train(self)

        # Start the game
        self.start_game()
