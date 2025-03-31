"""
Module for managing the game state for the client "I Like Trains"
"""

import logging
import time
import json
import threading


window_lock = threading.Lock()
# Configure the logger
logger = logging.getLogger("client.game_state")


class GameState:
    """Class responsible for managing the game state"""

    def __init__(self, client, activate_agent):
        """Initialize the game state manager with a reference to the client"""
        self.client = client
        self.activate_agent = activate_agent
        self.lock = (
            threading.Lock()
        )  # Add a threading lock to prevent concurrency issues

    def handle_state_data(self, data):
        """Handle game state data received from the server"""
        try:
            if not isinstance(data, dict):
                logger.warning("Received non-dictionary state data: " + str(data))
                return

            # logger.debug(f"Received state data: {data}")
            # Update game data only if present in the packet
            if "trains" in data:
                # Update only the modified trains
                for train_name, train_data in data["trains"].items():
                    if train_name not in self.client.trains:
                        self.client.trains[train_name] = {}
                    # Update the modified attributes
                    # logger.debug(f"Updating train {train_name} with {train_data}")
                    self.client.trains[train_name].update(train_data)

                if self.activate_agent:
                    self.client.agent.all_trains = self.client.trains

            # Handle renamed train
            if "rename_train" in data:
                old_name, new_name = data["rename_train"]
                if old_name in self.client.trains:
                    logger.info(f"Renaming train {old_name} to {new_name}")
                    self.client.trains[new_name] = self.client.trains.pop(old_name)
                    if self.activate_agent:
                        self.client.agent.all_trains = self.client.trains

            if "passengers" in data:
                # Adjust passenger positions to be in pixel coordinates
                self.client.passengers = data["passengers"]
                if self.activate_agent:
                    self.client.agent.passengers_data = self.client.passengers

            if "delivery_zone" in data:
                # Update delivery zone
                logger.debug(f"Delivery zone updated: {data['delivery_zone']}")
                self.client.delivery_zone = data["delivery_zone"]
                if self.activate_agent:
                    self.client.agent.delivery_zone = self.client.delivery_zone

            if "size" in data:
                self.client.game_width = data["size"]["game_width"]
                self.client.game_height = data["size"]["game_height"]
                logger.info(
                    f"Game size updated: {self.client.game_width}x{self.client.game_height}"
                )
                try:
                    # Recalculate screen dimensions
                    self.client.screen_width = (
                        self.client.leaderboard_width
                        + self.client.game_width
                        + 2.5 * self.client.game_screen_padding
                    )
                    self.client.screen_height = max(
                        self.client.game_height + 2 * self.client.game_screen_padding,
                        self.client.leaderboard_height,
                    )

                    logger.info(
                        f"Updated game dimensions: game width = {self.client.game_width}, screen width = {self.client.screen_width}"
                    )

                    # Schedule window update instead of directly creating the window
                    # This will be handled by the main thread
                    self.client.update_game_window_size(
                        self.client.screen_width, self.client.screen_height
                    )

                    # Mark as initialized to prevent default window creation
                    self.client.is_initialized = True
                    if self.activate_agent:
                        self.client.agent.screen_width = self.client.screen_width
                        self.client.agent.screen_height = self.client.screen_height

                except Exception as e:
                    logger.error("Error handling game size update: " + str(e))

            if "cell_size" in data:
                self.client.cell_size = data["cell_size"]
                logger.info(f"Cell size updated: {self.client.cell_size}")
                if self.activate_agent:
                    self.client.agent.cell_size = self.client.cell_size

            # Update the agent's state
            if self.activate_agent:
                # Make sure any data not updated individually gets updated here
                if not hasattr(self.client.agent, "all_trains"):
                    self.client.agent.all_trains = self.client.trains
                if not hasattr(self.client.agent, "passengers_data"):
                    self.client.agent.passengers_data = self.client.passengers
                if not hasattr(self.client.agent, "cell_size"):
                    self.client.agent.cell_size = self.client.cell_size
                if not hasattr(self.client.agent, "game_width"):
                    self.client.agent.game_width = self.client.game_width
                if not hasattr(self.client.agent, "game_height"):
                    self.client.agent.game_height = self.client.game_height

                self.client.agent.update_agent()

        except Exception as e:
            logger.error("Error handling state data: " + str(e))

    def handle_leaderboard_data(self, data):
        """Handle leaderboard data received from the server"""
        logger.info("Received leaderboard data")
        try:
            # Check if data is a string and try to parse it as JSON
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    logger.error(
                        "Failed to parse leaderboard data as JSON: " + str(data)
                    )
                    return

            # Check that data is a list
            if not isinstance(data, list):
                logger.error("Leaderboard data is not a list: " + str(type(data)))
                return

            # Update leaderboard data
            self.client.leaderboard_data = data

            # Display the leaderboard in a separate window only if explicitly requested
            if (
                hasattr(self.client, "show_separate_leaderboard")
                and self.client.show_separate_leaderboard
            ):
                self.client.renderer.show_leaderboard_window(data)
        except Exception as e:
            logger.error("Error handling leaderboard data: " + str(e))

    def handle_waiting_room_data(self, data):
        """Handle waiting room data received from the server"""
        try:
            if not isinstance(data, dict):
                logger.error("Waiting room data is not a dictionary: " + str(data))
                return

            # Update waiting room data
            self.client.waiting_room_data = data

            self.client.leaderboard_height = data.get("nb_players") * 10
            # logger.debug("Waiting room data updated: ")

        except Exception as e:
            logger.error("Error handling waiting room data: " + str(e))

    def handle_death(self, data):
        """Handle cooldown data received from the server"""
        try:
            if not isinstance(data, dict):
                logger.error("Cooldown data is not a dictionary: " + str(data))
                return

            # Update the agent's cooldown data
            self.client.agent.is_dead = True
            self.client.agent.death_time = time.time()
            self.client.agent.waiting_for_respawn = True
            self.client.agent.respawn_cooldown = data.get("remaining", 0)
            # logger.info("Cooldown updated: " + str(self.client.agent.respawn_cooldown) + "s")
        except Exception as e:
            logger.error("Error handling cooldown data: " + str(e))

    def handle_game_status(self, data):
        """Gère la réception du statut du jeu"""
        try:
            game_started = data.get("game_started", False)
            if game_started:
                self.client.in_waiting_room = False
                logger.info("Game already started - joining ongoing game")
            else:
                self.client.in_waiting_room = True
                logger.info("Game not started - entering waiting room")
        except Exception as e:
            logger.error("Error handling game status: " + str(e))

    def handle_server_message(self, message):
        """Gère les messages reçus du serveur"""
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "waiting_room":
                self.handle_waiting_room_data(data)
            elif message_type == "game_status":
                self.handle_game_status(data)
            elif message_type == "game_over":
                self.handle_game_over(data)
            else:
                logger.warning("Unknown message type received: " + str(message_type))
        except Exception as e:
            logger.error("Error handling server message: " + str(e))

    def handle_drop_wagon_success(self, message):
        """Handle successful passenger drop response from server"""
        try:
            agent_name = message.get("agent_name", "")
            position = message.get("position", None)

            if agent_name == self.client.agent.agent_name:
                logger.info(f"Successfully dropped a passenger at position {position}")
                # The train state will be updated in the next state update
        except Exception as e:
            logger.error(f"Error handling drop passenger success: {e}")

    def handle_game_over(self, data):
        """Handle game over data received from the server"""
        try:
            logger.info("Game over received")

            # Store the game over data
            self.client.game_over = True
            self.client.game_over_data = data

            # Extract final scores
            self.client.final_scores = data.get("final_scores", [])

            # Update the leaderboard with final scores
            self.client.leaderboard_data = self.client.final_scores

            logger.info(f"Game over: {data.get('message', 'Time limit reached')}")
            logger.info(f"Final scores: {self.client.final_scores}")

        except Exception as e:
            logger.error(f"Error handling game over data: {e}")
