"""
AI client for the game "I Like Trains"
This module provides an AI client that can control trains on the server side
"""

import threading
import time
import logging
import sys
import os


# Add the client directory to the path so we can import the Agent class
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "client"))
from agent import Agent

logger = logging.getLogger("server.ai_client")


class AINetworkInterface:
    """
    A simple interface that mimics the NetworkManager class from the client
    but directly interacts with the game on the server side
    """

    def __init__(self, room, train_name):
        self.room = room
        self.train_name = train_name

    def send_direction_change(self, direction):
        """Change the direction of the train using the server's function"""
        # logger.debug(f"AI client {self.train_name} sending direction change: {direction}")
        if self.train_name in self.room.game.trains and self.room.game.is_train_alive(
            self.train_name
        ):
            self.room.game.trains[self.train_name].change_direction(direction)
            # logger.debug(f"AI client {self.train_name} changed direction to {direction}")
            return True
        else:
            logger.warning(f"Failed to change direction for train {self.train_name}")
        return False

    def send_drop_wagon_request(self):
        """Drop a wagon from the train using the server's function"""
        if self.train_name in self.room.game.trains and self.room.game.is_train_alive(
            self.train_name
        ):
            last_wagon_position = self.room.game.trains[self.train_name].drop_wagon()
            if last_wagon_position:
                # Create a new passenger at the position of the dropped wagon
                from passenger import Passenger

                new_passenger = Passenger(self.room.game)
                new_passenger.position = last_wagon_position
                new_passenger.value = 1
                self.room.game.passengers.append(new_passenger)
                self.room.game._dirty["passengers"] = True
                return True
        return False

    def send_spawn_request(self):
        """Request to spawn the train using the server's function"""
        logger.debug(f"AI client {self.train_name} sending spawn request")
        if self.train_name not in self.room.game.trains:
            cooldown = self.room.game.get_train_cooldown(self.train_name)
            if cooldown <= 0:
                return self.room.game.add_train(self.train_name)
        return False

    def send_start_game_request(self):
        """Not needed for server-side AI client"""
        return True


class AIClient:
    """
    AI client that controls a train on the server side
    using the Agent class from the client
    """

    def __init__(self, room, name):
        self.room = room
        self.game = room.game
        self.agent_name = name  # The AI agent name
        self.train_name = name  # Use the AI name as the train name

        # Create network interface
        self.network = AINetworkInterface(
            room, name
        )  # Use AI name for network interface

        # Create agent
        self.agent = Agent(
            name, self.network, "server.ai_agent", False
        )  # Use AI name for agent
        self.agent.delivery_zone = self.game.delivery_zone.get_state()

        # Start the AI thread
        self.running = True
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()

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
        self.passengers_data = []
        for passenger in self.game.passengers:
            self.passengers_data.append(
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
            try:
                # logger.debug(f"AI client {self.agent_name} running")
                # Update the client state from the game
                self.update_state()

                # logg the position of the train
                # logger.debug(f"AI client {self.agent_name} train position: {self.all_trains[self.agent_name]['position']}")

                # Make sure the agent has access to the correct properties
                self.agent.all_trains = self.all_trains
                self.agent.passengers_data = self.passengers_data
                self.agent.cell_size = self.cell_size
                self.agent.game_width = self.game_width
                self.agent.game_height = self.game_height

                # Update the agent
                self.agent.update_agent()

                # Add automatic respawn logic
                if (
                    not self.game.trains[self.agent_name].alive
                    and self.agent.waiting_for_respawn
                ):
                    # logger.debug(f"AI client {self.agent_name} is dead, waiting for respawn")
                    elapsed = time.time() - self.agent.death_time
                    if elapsed >= self.agent.respawn_cooldown:
                        logger.debug(
                            f"AI client {self.agent_name} respawn cooldown over, checking game state"
                        )
                        if self.in_waiting_room:
                            logger.debug(
                                f"AI client {self.agent_name} in waiting room, trying to start game"
                            )
                            # Start game if in waiting room
                            if (
                                not self.room.game_thread
                                or not self.room.game_thread.is_alive()
                            ):
                                if self.room.get_player_count() >= self.room.nb_players:
                                    self.room.start_game()

                        logger.debug(f"AI client {self.agent_name} trying to spawn")
                        cooldown = self.room.game.get_train_cooldown(self.agent_name)
                        if cooldown <= 0:
                            self.room.game.add_train(self.agent_name)
                            self.agent.waiting_for_respawn = False
                            self.agent.is_dead = False
                            logger.info(f"AI client {self.agent_name} respawned")

                # else:
                #     logger.debug(f"AI client {self.agent_name} is alive, waiting for next update")

                # Sleep to avoid high CPU usage
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in AI client {self.agent_name}: {e}")
                time.sleep(0.5)

    def stop(self):
        """Stop the AI client"""
        self.running = False
