import json
import logging
import random
import threading
import time
from tqdm import tqdm

from common.server_config import ServerConfig
from common import stats_manager
from common.constants import REFERENCE_TICK_RATE

from server.game import Game
from server.ai_client import AIClient

# Configure logger
logger = logging.getLogger("server.room")
logger.setLevel(logging.DEBUG)

# List of names for AI-controlled clients
AI_NAMES = [
    "Bot Adrian",
    "Bot Albert",
    "Bot Allen",
    "Bot Andy",
    "Bot Arnold",
    "Bot Bert",
    "Bot Cecil",
    "Bot Charles",
    "Bot Clarence",
    "Bot Elmer",
    "Bot Ernest",
    "Bot Felix",
    "Bot Frank",
    "Bot Fred",
    "Bot Gilbert",
    "Bot Gus",
    "Bot Hank",
    "Bot Howard",
    "Bot James",
    "Bot Lester",
]


class Room:
    # TODO(alok): remove nb_clients_max and use config.clients_per_room
    def __init__(
        self,
        config: ServerConfig,
        room_id,
        nb_players_max,
        running,
        server_socket,
        send_cooldown_notification,
        remove_room,
        addr_to_sciper,
        record_disconnection,
        tqdm_message=None,
    ):
        self.config = config
        self.id = room_id
        self.nb_players_max = nb_players_max
        self.running = running
        self.server_socket = server_socket
        self.send_cooldown_notification = send_cooldown_notification
        self.remove_room = remove_room
        self.addr_to_sciper = addr_to_sciper
        self.record_disconnection = record_disconnection
        self.tqdm_message = tqdm_message

        # Initialize random seed if provided in config, otherwise generate one
        if self.config.seed is None:
            self.seed = random.randint(0, 2**32 - 1)
        else:
            self.seed = self.config.seed
        self.random = random.Random(self.seed)

        logger.debug(f"Room {self.id} created with seed {self.seed}")

        self.clients = {}  # {addr: nickname}
        self.client_game_modes = {}  # {addr: game_mode}
        self.game_thread = None

        self.game_over = False  # Track if the game is over
        self.room_creation_time = time.time()  # Track when the room was created
        self.first_client_join_time = None  # Track when the first client joins
        self.stop_waiting_room = False  # Flag to stop the waiting room thread - Initialized BEFORE thread start

        self.waiting_room_thread = threading.Thread(target=self.broadcast_waiting_room)
        self.waiting_room_thread.daemon = True
        self.waiting_room_thread.start()

        self.tick_counter = 0  # Track the number of ticks since game start

        self.used_ai_names = set()  # Track AI names that are already in use
        self.ai_clients = {}  # Maps train names to AI clients
        self.AI_NAMES = AI_NAMES  # Store the AI names as an instance attribute
        self.used_nicknames = set(self.clients.keys())

        self.game = Game(
            self.config,
            self.send_cooldown_notification,
            self.nb_players_max,
            self.id,
            self.seed,
            self.random,
        )

        logger.debug(f"Room {room_id} created with number of clients {nb_players_max}")

    def start_game(self):
        logger.debug("Starting game...")

        # Stop the waiting room thread by setting the flag
        self.stop_waiting_room = True
        # self.waiting_room_thread.join() # Cannot join from the same thread

        if self.game_thread:
            return

        # Reset tick counter            
        self.game.start_time = time.time()  # Start at tick 0
        self.game.game_started = True
        self.game.start_time_ticks = 0
        self.game.current_tick = 0

        logger.info(f"Game started in room {self.id} at tick {self.tick_counter}")
        # log all clients
        logger.info(f"Clients in room {self.id}: {self.clients}")

        # Send game_started_success message - Moved before the grading mode check
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
                self.server_socket.sendto(
                    (json.dumps(response) + "\n").encode(), client_addr
                )
            except Exception as e:
                logger.error(f"Error sending start success to client: {e}")
        
        # In grading mode, we add all configured agents to the game
        if self.config.grading_mode:
            logger.debug("Starting game in grading mode")
            if len(self.config.agents) > 0:
                # Clear any existing AI clients first to avoid duplicates
                self.ai_clients = {}
                self.game.ai_clients = {}
                
                # Add all configured agents
                for agent in self.config.agents:
                    ai_nickname = self.get_available_ai_name(agent)
                    ai_agent_file_name = agent.agent_file_name
                    logger.debug(f"Adding AI client {ai_nickname} with agent {ai_agent_file_name}")
                    self.add_ai(ai_nickname=ai_nickname, ai_agent_file_name=ai_agent_file_name)
            else:
                logger.warning("No agents configured in config.json for grading mode")
        else:
            # In normal mode, we add all human players to the game first and then add bots if needed
            logger.debug("Starting game in normal mode")
            
            self.add_all_trains()
            
            current_players = self.get_player_count()
            nb_bots_needed = self.nb_players_max - current_players
            self.fill_with_bots(nb_bots_needed)

            for ai_name, ai_client in self.game.ai_clients.items():
                if ai_name not in self.game.trains:
                    logger.debug(f"Adding train for AI client {ai_name}")
                
                # Log train status
                if ai_name in self.game.trains:
                    logger.debug(f"Train {ai_name} initialized at position {self.game.trains[ai_name].position}")
                else:
                    logger.warning(f"Failed to add train for AI client {ai_name}")
        
        # In grading mode, we run the simulation directly in this thread
        # Create and start game thread
        self.game_thread = threading.Thread(target=self.run_game)
        self.game_thread.daemon = True
        self.game_thread.start()

        logger.debug(
            f"Game started in room {self.id} with {len(self.clients)} clients"
        )
            
    def run_game(self):
        """Run the game in grading mode - directly in the room thread without using broadcast_game_state"""
        # Define the standard tick rate (for reference)
        reference_tickrate = REFERENCE_TICK_RATE
        
        # Calculate total number of updates based on the standard tickrate
        # This ensures that game duration is consistent regardless of the configured tickrate
        total_updates = int(self.config.game_duration_seconds * reference_tickrate)
        
        # Calculate how much game time passes per tick (in seconds)
        game_seconds_per_tick = 1.0 / reference_tickrate
        
        # Calculate how much real time should pass per tick (in seconds)
        real_seconds_per_tick = 1 / self.config.tick_rate
        
        # Log the timing information
        if self.config.tick_rate == reference_tickrate:
            speed_description = "normal speed"
        elif self.config.tick_rate > reference_tickrate:
            speed_description = f"{self.config.tick_rate/reference_tickrate:.1f}x faster than normal"
        else:
            speed_description = f"{reference_tickrate/self.config.tick_rate:.1f}x slower than normal"
            
        logger.debug(f"Game running at {speed_description} (tickrate: {self.config.tick_rate}).")
        logger.debug(f"Acceleration in comparison to reference tickrate: {self.config.tick_rate / reference_tickrate:.2f}")
        logger.debug(f"Game seconds per tick: {game_seconds_per_tick:.4f}s")
        logger.debug(f"Real seconds per tick: {real_seconds_per_tick*1000:.2f}ms")
        
        # Initialize game time to zero
        game_time_elapsed = 0.0
        
        # Store the actual game start time for real-time tracking
        game_start_time = time.time()
        
        # Run the simulation for the calculated number of ticks
        # Use tqdm progress bar only in grading mode
        if self.config.grading_mode:
            iteration_range = tqdm(range(total_updates), desc=self.tqdm_message, unit="ticks")
        else:
            iteration_range = range(total_updates)
            
        for update_count in iteration_range:
            if not self.running or self.game_over:
                break
                
            # Synchronize update_count and tick_counter
            self.tick_counter = update_count + 1
            self.game.current_tick = self.tick_counter
            
            # Update game time - this is completely independent of real time
            # Each tick represents a fixed amount of game time
            game_time_elapsed += game_seconds_per_tick

            # Update game state
            self.game.update()
            
            # Calculate remaining game time
            remaining_game_time = self.config.game_duration_seconds - game_time_elapsed
            
            # Prepare the game state to send to clients
            state = self.game.get_dirty_state()
            
            # Add remaining time to state data only if it has changed significantly
            if self.game.last_remaining_time is None or round(remaining_game_time) != round(self.game.last_remaining_time):
                state["remaining_time"] = round(remaining_game_time)
                self.game.last_remaining_time = remaining_game_time

            # Create the data packet
            state_data = {"type": "state", "data": state}

            if state:  # If data has been modified
                # Update all AI clients
                for ai_client in self.ai_clients.values():
                    ai_client.update_state(state_data)
                
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

                        self.server_socket.sendto(
                            state_json.encode(), client_addr
                        )
                    except Exception as e:
                        logger.error(f"Error sending state to client: {e}")
            
            # Sleep if necessary to maintain the desired tick rate in real time
            # Skip sleep in grading mode to run as fast as possible
            if not self.config.grading_mode:
                if real_seconds_per_tick > 0:
                    # Calculate elapsed real time since game start
                    elapsed_real_time = time.time() - game_start_time
                    # Calculate target real time based on current update count and target tick rate
                    target_real_time = (update_count + 1) * real_seconds_per_tick
                    # Calculate time to sleep to catch up with the target time
                    time_to_sleep = max(0, target_real_time - elapsed_real_time)
                    
                    if time_to_sleep > 0:
                        time.sleep(time_to_sleep)
                else:
                    # log that the loop is late
                    logger.warning(f"Game loop is late by {-time_to_sleep:.2f} seconds")

        # Game has finished
        end_time = time.time()
        total_real_time = end_time - game_start_time
        logger.info(f"Game completed in {total_real_time:.2f} real seconds")
        logger.info(f"Game time elapsed: {game_time_elapsed:.2f} seconds")
        logger.info(f"Time ratio: {game_time_elapsed/total_real_time:.2f}x")
        logger.info(f"Actual ticks completed: {self.tick_counter}")
        logger.info(f"Ticks per second: {self.tick_counter/total_real_time:.1f}")
        logger.info(f"Final scores: {self.game.best_scores}")

        logger.info(f"Game in room {self.id} ending after {self.tick_counter} ticks, game time: {game_time_elapsed:.2f}s, real time: {total_real_time:.2f}s")
        self.end_game()

    def end_game(self):
        """End the game and send final scores to all clients"""
        if self.game_over:
            return  # Game already ended

        self.game_over = True

        # Collect final scores
        final_scores = []

        # log the best scores
        logger.debug(f"Best scores: {self.game.best_scores}")

        participant_scores = []  # List of tuples: (id, score, is_human)
        for nickname, best_score in self.game.best_scores.items():
            logger.debug(f"Train {nickname} has best score {best_score}")

            # Find the client address associated with this train name
            client_addr = None
            for addr, name in self.clients.items():
                if name == nickname:
                    client_addr = addr
                    break

            final_scores.append({"name": nickname, "best_score": best_score})

            # Update best score in the scores file
            # if self.game.high_score_all_time.update(nickname, best_score):
            #     scores_updated = True
            #     logger.info(f"Updated best score for {nickname}: {best_score}")

            participant_id = None
            is_human = False
            # Check if it's a human player
            found_human = False
            for addr, name in self.clients.items():
                if name == nickname:
                    sciper = self.addr_to_sciper.get(addr)
                    if sciper:
                        participant_id = sciper
                        is_human = True
                        found_human = True
                        break
            # If not found as human, assume it's an AI
            if not found_human:
                participant_id = nickname  # Use name as ID for bots
                is_human = False

            if participant_id:
                participant_scores.append((participant_id, best_score, is_human))

        # --- Record Bot vs Human Scores ---
        human_players = [(p_id, score) for p_id, score, is_human in participant_scores if is_human]
        bot_players = [(p_id, score) for p_id, score, is_human in participant_scores if not is_human]

        if human_players and bot_players:
            logger.debug(f"Recording bot vs human scores for room {self.id}")
            for human_id, human_score in human_players:
                for bot_id, bot_score in bot_players:
                    logger.debug(f"  Recording: Human {human_id} ({human_score}) vs Bot {bot_id} ({bot_score})")
                    stats_manager.record_bot_vs_human_score(human_id, bot_id, human_score, bot_score)
        # -----------------------------------

        # --- Stats: Record Game Results ---
        if final_scores:
            logger.debug(f"Recording game results for final scores: {final_scores}")
            winner_nickname = final_scores[0]["name"]

            # We only need the winner's nickname and whether they are AI for context
            winner_is_ai = winner_nickname in self.ai_clients

            for i, score_entry in enumerate(final_scores):
                logger.debug(f"Processing score entry {i}: {score_entry}")
                nickname = score_entry["name"]
                addr = next((a for a, n in self.clients.items() if n == nickname), None)
                is_ai = nickname in self.ai_clients

                # --- Skip AI players for stat recording ---
                if is_ai:
                    logger.debug(f"Skipping stats for AI player {nickname}")
                    continue  # Only record stats for human players

                # --- Get Human Player Info ---
                if not addr:  # Should only happen if human client disconnected *during* end_game processing?
                    logger.warning(
                        f"Stats: Could not find address for player {nickname} in room {self.id}. Skipping stats."
                    )
                    continue

                # Get sciper from the server instance using the address
                player_sciper = self.addr_to_sciper.get(addr)
                logger.debug(
                    f"Stats: Found sciper {player_sciper} for human player {nickname} ({addr})"
                )

                if not player_sciper:
                    logger.warning(
                        f"Stats: Could not find sciper for human player {nickname} ({addr}). Skipping stats."
                    )
                    continue

                # --- Determine Opponent Context ---
                is_winner = nickname == winner_nickname
                opponent_nickname = "N/A"
                opponent_is_bot = False

                logger.debug(
                    f"Stats: Determining opponent context for {nickname} - is winner: {is_winner}"
                )

                if is_winner:
                    logger.debug(
                        f"Human player {nickname} is a winner - finding opponent"
                    )
                    # Winner: Find highest scoring opponent for context (can be human or AI)
                    if len(final_scores) > 1:
                        logger.debug(
                            f"Multiple human players in room {self.id} - finding highest scoring opponent"
                        )
                        opponent_score_entry = final_scores[1]
                        opponent_nickname = opponent_score_entry["name"]
                        opponent_is_bot = opponent_nickname in self.ai_clients
                    else:
                        logger.debug(
                            f"Only one human player in room {self.id} - no opponent"
                        )
                        opponent_nickname = "No Opponent"
                        opponent_is_bot = False  # No opponent
                else:
                    logger.debug(
                        f"Human player {nickname} is a loser - opponent is {winner_nickname}"
                    )
                    # Loser: Opponent context is the winner
                    opponent_nickname = winner_nickname
                    opponent_is_bot = winner_is_ai

                # --- Record Stats ---
                try:
                    logger.debug(
                        f"Recording game result for sciper {player_sciper} - win: {is_winner}, opponent: {opponent_nickname}, opponent is bot: {opponent_is_bot}"
                    )
                    stats_manager.record_game_result(
                        sciper=player_sciper,
                        win=is_winner,
                        opponent_is_bot=opponent_is_bot,
                        opponent_name=opponent_nickname,
                    )
                except Exception as e:
                    logger.error(
                        f"Stats: Failed to record game result for {player_sciper}: {e}"
                    )

        # === Record last match scores for all pairs ===
        logger.debug(
            f"Recording last match scores for all pairs. Participants: {participant_scores}"
        )
        if len(participant_scores) >= 2:
            for i in range(len(participant_scores)):
                for j in range(i + 1, len(participant_scores)):
                    id1, score1, is_human1 = participant_scores[i]
                    id2, score2, is_human2 = participant_scores[j]

                    # Call record_bot_vs_human_score ONLY for human vs bot pairs
                    if is_human1 and not is_human2:
                        stats_manager.record_bot_vs_human_score(
                            human_sciper=id1, bot_nickname=id2, human_score=score1, bot_score=score2
                        )
                    elif not is_human1 and is_human2:
                        stats_manager.record_bot_vs_human_score(
                            human_sciper=id2, bot_nickname=id1, human_score=score2, bot_score=score1
                        )
                    # No call for human-human or bot-bot pairs as last_match_scores was removed

        # Save scores if any were updated
        # if scores_updated:
        #     self.game.high_score_all_time.save()

        # Create game over message
        game_over_data = {
            "type": "game_over",
            "data": {
                "message": "Game is over. Time limit reached.",
                "final_scores": final_scores,
                "duration": self.config.game_duration_seconds,
                "best_scores": self.game.best_scores,
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

                self.server_socket.sendto(state_json.encode(), client_addr)
            except Exception as e:
                logger.error(f"Error sending game over data to client: {e}")

        self.game.running = False

        # Record disconnection stats for all human clients at game end
        # This ensures playtime is recorded even if clients disconnect without proper notification
        for addr in list(self.clients.keys()):
            # Skip AI clients
            if isinstance(addr, tuple) and len(addr) == 2 and addr[0] == "AI":
                continue
                
            # Call handle_client_disconnection for human clients
            try:
                logger.info(f"Recording end-of-game stats for client at {addr}")
                self.record_disconnection(self.addr_to_sciper[addr], "game_over")
            except Exception as e:
                logger.error(f"Error recording end-of-game stats for {addr}: {e}")

        # Close the room after a short delay to ensure all clients receive the game over message
        def close_room_after_delay():
            time.sleep(
                2
            )  # Wait 2 seconds to ensure clients receive the game over message
            logger.debug(f"Closing room {self.id} after game over")
            self.running = False
            # Remove the room from the server
            self.remove_room(self.id)

        # Start a thread to close the room after a delay
        close_thread = threading.Thread(target=close_room_after_delay)
        close_thread.daemon = True
        close_thread.start()

    def is_full(self):
        nb_players = self.get_player_count()
        return nb_players >= self.nb_players_max

    def get_players(self):
        return [
            self.clients[addr]
            for addr in self.clients
            if addr in self.client_game_modes
            and self.client_game_modes[addr] != "observer"
        ]

    def get_player_count(self):
        return len(
            [mode for mode in self.client_game_modes.values() if mode != "observer"]
        )

    def get_observer_count(self):
        return len(
            [mode for mode in self.client_game_modes.values() if mode == "observer"]
        )

    def broadcast_waiting_room(self):
        """Broadcast waiting room data to all clients"""
        last_update = time.time()
        while self.running and not self.stop_waiting_room:
            if (self.clients or self.config.grading_mode) and not self.game_thread:
                if self.is_full():
                    logger.info("Room is full")
                    self.start_game()
                    continue

                current_time = time.time()
                if (
                    current_time - last_update >= 1.0 / REFERENCE_TICK_RATE
                ):  # Limit to TICK_RATE Hz
                    # Calculate remaining time before adding bots
                    remaining_time = 0
                    if self.clients:
                        # Use the time the first client joined if available, otherwise creation time
                        start_time = (
                            self.first_client_join_time
                            if self.first_client_join_time is not None
                            else self.room_creation_time
                        )
                        elapsed_time = current_time - start_time
                        remaining_time = max(
                            0,
                            self.config.waiting_time_before_bots_seconds
                            - elapsed_time,
                        )

                    # If time is up and room is not full, add bots and start the game
                    if (remaining_time == 0) and not self.game_thread:
                        logger.info(
                            f"Waiting time expired for room {self.id}, adding bots and starting game"
                        )
                        self.start_game()

                    if self.config.grading_mode:
                        last_update = current_time
                        continue
                    
                    waiting_room_data = {
                        "type": "waiting_room",
                        "data": {
                            "room_id": self.id,
                            "players": list(self.get_players()),
                            "nb_players": self.nb_players_max,
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

                            self.server_socket.sendto(state_json.encode(), client_addr)
                        except Exception as e:
                            logger.error(
                                f"Error sending waiting room data to client: {e}"
                            )

                    last_update = current_time

            # Sleep for half the period
            time.sleep(1.0 / (REFERENCE_TICK_RATE * 2))
            # except Exception as e:
            #     logger.error(f"Error in broadcast_waiting_room: {e}")
            #     time.sleep(1.0 / self.config.tick_rate)

    def broadcast_game_state(self):
        """Thread that periodically sends the game state to clients"""
        # Send initial state to all clients
        initial_state = {
            "type": "initial_state",
            "data": {
                "game_life_time": self.config.game_duration_seconds,
                "start_time": time.time(),  # Send server start time for synchronization
            },
        }

        initial_state_json = json.dumps(initial_state) + "\n"
        for client_addr in list(self.clients.keys()):
            logger.debug(f"Sending initial state to {client_addr}")
            try:
                # Skip AI clients - they don't need network messages
                if (
                    isinstance(client_addr, tuple)
                    and len(client_addr) == 2
                    and client_addr[0] == "AI"
                ):
                    continue
                self.server_socket.sendto(initial_state_json.encode(), client_addr)
            except Exception as e:
                logger.error(f"Error sending initial state to client: {e}")

        last_update = time.time()
        while self.running:
            try:
                # Calculate the time elapsed since the last update
                current_time = time.time()
                elapsed = current_time - last_update

                # If enough time has passed
                if elapsed >= 1.0 / REFERENCE_TICK_RATE:
                    # Get the game state with only the modified data
                    state = self.game.get_dirty_state()
                    if state:  # If data has been modified
                        # Add remaining time to state data only if it has changed significantly (rounded to nearest second)
                        remaining_seconds = self.config.game_duration_seconds - (self.tick_counter / REFERENCE_TICK_RATE)
                        current_remaining_time_rounded = round(remaining_seconds)
                        if self.game.last_remaining_time is None or current_remaining_time_rounded != round(self.game.last_remaining_time):
                            logger.debug(f"Remaining time changed: {remaining_seconds}")
                            state["remaining_time"] = remaining_seconds
                            self.game.last_remaining_time = remaining_seconds

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

                                self.server_socket.sendto(
                                    state_json.encode(), client_addr
                                )
                            except Exception as e:
                                logger.error(f"Error sending state to client: {e}")

                    last_update = current_time

                # Wait a bit to avoid overloading the CPU
                time.sleep(1.0 / (REFERENCE_TICK_RATE * 2))
            except Exception as e:
                logger.error(f"Error in broadcast_game_state: {e}")
                time.sleep(1.0 / REFERENCE_TICK_RATE)

    def fill_with_bots(self, nb_bots_needed):
        """Fill the room with bots and start the game"""
        if nb_bots_needed <= 0:
            return

        logger.info(f"Adding {nb_bots_needed} bots to room {self.id}")

        # If we need less bots or an equal number to the available list, we pick the bots
        # randomly (without repetition).
        # If we need more, we pick each one at least once.
        agents = self.config.agents[:]
        random.shuffle(agents)
        while len(agents) < nb_bots_needed:
            agents.append(random.choice(self.config.agents))
        agents = agents[:nb_bots_needed]

        for agent in agents:
            ai_nickname = self.get_available_ai_name(agent)
            ai_agent_file_name = agent.agent_file_name
            self.add_ai(ai_nickname=ai_nickname, ai_agent_file_name=ai_agent_file_name)

    def get_available_ai_name(self, agent):
        """Get an available AI name that is not already in use"""
        ai_nickname = agent.nickname

        if ai_nickname is None or ai_nickname == "":
            for name in self.AI_NAMES:
                if name not in self.used_ai_names:
                    self.used_ai_names.add(name)
                    return name

            # If all names are used, create a generic name with a random number
            logger.debug("All AI names are used, creating a generic name")
            ai_nickname = f"Bot {random.randint(1000, 9999)}"
            self.used_ai_names.add(ai_nickname)

        # If the nickname is already used, generate a new one
        while ai_nickname in self.used_nicknames:
            r = random.randint(1, 999)
            ai_nickname = f"{ai_nickname}-{r}"

        self.used_nicknames.add(ai_nickname)

        return ai_nickname

    def add_ai(self, ai_nickname=None, ai_agent_file_name=None):
        """Create an AI client to control a train"""

        # Creating a new AI train (not replacing an existing one)
        logger.debug(f"Creating new AI train with name {ai_nickname}")

        # Add the train to the game
        if self.game.add_train(ai_nickname):
            # Add the AI client to the room
            self.clients[("AI", ai_nickname)] = ai_nickname

            # Import the AI agent from the config path
            logger.debug(
                f"Creating AI client {ai_nickname} using agent from {ai_agent_file_name}"
            )

            self.ai_clients[ai_nickname] = AIClient(
                self, ai_nickname, ai_agent_file_name, is_grading_mode=self.config.grading_mode
            )

            # Add the ai_client to the game
            self.game.ai_clients[ai_nickname] = self.ai_clients[ai_nickname]

            logger.debug(f"Added new AI train {ai_nickname} to room {self.id}")
            return ai_nickname
        else:
            logger.error(f"Failed to add new AI train {ai_nickname} to game")
            return None

    def replace_player_by_ai(self, train_nickname_to_replace):
        # Check if there's already an AI controlling this train
        if train_nickname_to_replace in self.ai_clients:
            logger.warning(f"AI already exists for train {train_nickname_to_replace}")
            return

        logger.debug(f"Creating AI client for train {train_nickname_to_replace}")

        # Change the train's name in the game
        if train_nickname_to_replace in self.game.trains:
            # Get a random agent from config
            agent = random.choice(self.config.agents)
            ai_nickname = self.get_available_ai_name(agent)
            ai_agent_file_name = agent.agent_file_name
            is_dead = not self.game.trains[train_nickname_to_replace].alive

            # Save the train's color
            if train_nickname_to_replace in self.game.train_colors:
                train_color = self.game.train_colors[train_nickname_to_replace]
                self.game.train_colors[ai_nickname] = train_color
                del self.game.train_colors[train_nickname_to_replace]

            # Get the train object
            train = self.game.trains[train_nickname_to_replace]

            # Update the train's name
            train.nickname = ai_nickname

            # Move the train to the new key in the dictionary
            self.game.trains[ai_nickname] = train
            del self.game.trains[train_nickname_to_replace]
            logger.debug(
                f"Moved train {train_nickname_to_replace} to {ai_nickname} in game"
            )

            # Notify clients about the train rename
            state_data = {
                "type": "state",
                "data": {"rename_train": [train_nickname_to_replace, ai_nickname]},
            }

            state_json = json.dumps(state_data) + "\n"
            # Iterate over a copy of the client addresses to avoid issues if the list changes
            # Only send to non-AI clients
            for client_addr in list(self.clients.keys()):
                # Ensure it's a real client address tuple (IP, port), not an AI marker
                if (
                    isinstance(client_addr, tuple)
                    and len(client_addr) == 2
                    and isinstance(client_addr[1], int)
                ):
                    try:
                        self.server_socket.sendto(state_json.encode(), client_addr)
                    except Exception as e:
                        # Log error but continue trying other clients
                        logger.error(
                            f"Error sending train rename notification to client {client_addr}: {e}"
                        )

            # Create the AI client with the new name
            self.ai_clients[ai_nickname] = AIClient(
                self, ai_nickname, ai_agent_file_name, is_dead, is_dead, is_grading_mode=self.config.grading_mode
            )

            # Add the AI client to the game
            self.game.ai_clients[ai_nickname] = self.ai_clients[ai_nickname]

            # Prepare the game state to send to clients
            state = self.game.get_state()

            # Create the data packet
            state_data = {"type": "state", "data": state}

            self.ai_clients[ai_nickname].update_state(state_data)

        else:
            logger.warning(
                f"Train {train_nickname_to_replace} not found in game, cannot create AI client"
            )

    def add_all_trains(self):
        # Add trains for all the players
        for nickname in self.get_players():
            # Find the client address for this nickname
            client_addr = None
            for addr, name in self.clients.items():
                if name == nickname:
                    client_addr = addr
                    break

            if client_addr is None:
                logger.warning(f"Could not find address for player {nickname}")
                continue

            if self.game.add_train(nickname):
                response = {"type": "spawn_success", "nickname": nickname}
                self.server_socket.sendto(
                    (json.dumps(response) + "\n").encode(), client_addr
                )
            else:
                logger.warning(f"Failed to spawn train {nickname}")
                # Inform the client of the failure
                response = {
                    "type": "respawn_failed",
                    "message": "Failed to spawn train",
                }
                self.server_socket.sendto(
                    (json.dumps(response) + "\n").encode(), client_addr
                )
