"""
AI client for the game "I Like Trains"
This module provides an AI client that can control trains on the server side
"""

import threading
import time
import logging
from server.passenger import Passenger
import importlib


logger = logging.getLogger("server.ai_client")


class AINetworkInterface:
    """
    Mimics the NetworkManager class from the client but directly interacts with
    the game on the server side.
    """

    def __init__(self, room, nickname):
        self.room = room
        self.nickname = nickname

    def send_direction_change(self, direction):
        """Change the direction of the train using the server's function"""
        if self.room.game.contains_train(
            self.nickname
        ):
            self.room.game.trains[self.nickname].change_direction(direction)
            return True
        else:
            logger.error(
                f"Failed to change direction for train {self.nickname}. Train is in game: {self.nickname in self.room.game.trains}"
            )
        return False

    def send_drop_wagon_request(self):
        """Drop a wagon from the train using the server's function"""
        if self.nickname in self.room.game.trains and self.room.game.contains_train(
            self.nickname
        ):
            last_wagon_position = self.room.game.trains[self.nickname].drop_wagon()
            if last_wagon_position:
                # Create a new passenger at the position of the dropped wagon
                new_passenger = Passenger(self.room.game)
                new_passenger.position = last_wagon_position
                new_passenger.value = 1
                self.room.game.passengers.append(new_passenger)
                self.room.game._dirty["passengers"] = True
                return True
        return False

    def send_spawn_request(self):
        """Request to spawn the train using the server's function"""
        logger.debug(f"AI client {self.nickname} sending spawn request")
        if self.nickname not in self.room.game.trains:
            cooldown = self.room.game.get_train_cooldown(self.nickname)
            if cooldown <= 0:
                return self.room.game.add_train(self.nickname)
        return False


class AIClient:
    """
    AI client that controls a train on the server side
    using the Agent class from the client
    """

    def __init__(self, room, nickname, ai_agent_file_name=None, waiting_for_respawn=False, is_dead=False):
        """Initialize the AI client"""
        logger.debug(f"Initializing AI client {nickname}, waiting_for_respawn: {waiting_for_respawn}, is_dead: {is_dead}")
        self.room = room
        self.game = room.game
        self.nickname = nickname  # The AI agent name

        self.is_dead = is_dead
        self.waiting_for_respawn = waiting_for_respawn
        self.death_time = 0
        self.respawn_cooldown = 0

        # Create network interface
        self.network = AINetworkInterface(
            room, nickname
        )  # Use AI name for network interface

        # Initialize agent if path_to_agent is provided
        try:
            logger.info(f"Trying to import AI agent for {nickname}")
            if ai_agent_file_name.endswith(".py"):
                # Remove .py extension
                ai_agent_file_name = ai_agent_file_name[:-3]

            # Construct the module path correctly
            module_path = f"common.agents.{ai_agent_file_name}"
            logger.info(f"Importing module: {module_path}")

            module = importlib.import_module(module_path)
            self.agent = module.Agent(nickname, self.network, logger="server.ai_agent")
            logger.info(f"AI agent {nickname} initialized using {ai_agent_file_name}")

        except ImportError as e:
            logger.error(f"Failed to import AI agent for {nickname}: {e}")
            raise e
        except Exception as e:
            logger.error(f"Failed to import AI agent for {nickname}: {e}")
            raise e

        self.agent.delivery_zone = self.game.delivery_zone.to_dict()

        # Start the AI thread
        self.running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"AI client {nickname} started")

        self.update_state()

    def update_state(self):
        """Update the state from the game"""
        # Format trains in the expected format for the agent
        self.all_trains = {}
        for name, train in self.game.trains.items():
            self.all_trains[name] = {
                "name": name,
                "position": train.position,
                "direction": train.direction,
                "wagons": train.wagons,
                "score": train.score,
                "alive": train.alive,
            }

        # Format passengers in the expected format for the agent
        self.passengers = []
        for passenger in self.game.passengers:
            self.passengers.append(
                {"position": passenger.position, "value": passenger.value}
            )

        # Copy other game state properties
        self.cell_size = self.game.cell_size
        self.game_width = self.game.game_width
        self.game_height = self.game.game_height
        self.in_waiting_room = not self.game.game_started

    def run(self):
        """Main AI client loop"""
        while self.running and self.room.running:
            # try:
            # Update the client state from the game
            self.update_state()

            # Make sure the agent has access to the correct properties
            self.agent.all_trains = self.all_trains
            self.agent.passengers = self.passengers
            self.agent.cell_size = self.cell_size
            self.agent.game_width = self.game_width
            self.agent.game_height = self.game_height

            # Update agent state only if train is alive and game contains train
            if not self.is_dead and self.game.contains_train(self.nickname):
                self.agent.update_agent()

            # Add automatic respawn logic
            # logger.debug(f"Is dead: {self.is_dead}, waiting for respawn: {self.waiting_for_respawn}")
            if (
                self.is_dead
                and self.waiting_for_respawn
            ):
                # logger.debug(f"AI client {self.nickname} waiting for respawn")
                elapsed = time.time() - self.death_time
                if elapsed >= self.respawn_cooldown:
                    # logger.debug(
                    #     f"AI client {self.nickname} respawn cooldown over, checking game state"
                    # )
                    if self.in_waiting_room:
                        logger.debug(
                            f"AI client {self.nickname} in waiting room, trying to start game"
                        )
                        # Start game if in waiting room
                        if (
                            not self.room.game_thread
                            or not self.room.game_thread.is_alive()
                        ):
                            if self.room.get_player_count() >= self.room.nb_players_max:
                                self.room.start_game()

                    logger.debug(f"AI client {self.nickname} trying to spawn")
                    cooldown = self.room.game.get_train_cooldown(self.nickname)
                    if cooldown <= 0:
                        self.room.game.add_train(self.nickname)
                        self.waiting_for_respawn = False
                        self.is_dead = False
                        logger.info(f"AI client {self.nickname} respawned")

            # else:
            #     logger.debug(f"AI client {self.nickname} is alive, waiting for next update")

            # Sleep to avoid high CPU usage
            time.sleep(0.1)
            # except Exception as e:
            #     logger.error(f"Error in AI client {self.nickname}: {e}")
            #     time.sleep(0.5)

    def stop(self):
        """Stop the AI client"""
        self.running = False
