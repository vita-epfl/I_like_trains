"""
AI client for the game "I Like Trains"
This module provides an AI client that can control trains on the server side
"""

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
        # logger.debug(f"AI client {self.nickname} sending spawn request")
        if self.nickname not in self.room.game.trains:
            cooldown = self.room.game.get_train_respawn_cooldown(self.nickname)
            if cooldown <= 0:
                return self.room.game.add_train(self.nickname)
        return False


class AIClient:
    """
    AI client that controls a train on the server side
    using the Agent class from the client
    """

    def __init__(self, room, nickname, ai_agent_file_name=None, waiting_for_respawn=False, is_dead=False, agent_dir=None):
        """Initialize the AI client
        
        Args:
            room: The room the AI client is in
            nickname: The nickname of the AI client
            ai_agent_file_name: The filename of the agent implementation
            waiting_for_respawn: Whether the AI is waiting for respawn
            is_dead: Whether the AI is dead
            agent_dir: The directory of the agent implementation
        """
        # logger.debug(f"Initializing AI client {nickname}, waiting_for_respawn: {waiting_for_respawn}, is_dead: {is_dead}")
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
            # logger.info(f"Trying to import AI agent for {nickname}")
            # Check if module_path is defined
            if ai_agent_file_name.endswith(".py"):
                # Remove .py extension
                ai_agent_file_name = ai_agent_file_name[:-3]

            module = importlib.import_module(agent_dir + "." + ai_agent_file_name)
            self.agent = module.Agent(nickname, self.network, logger="server.ai_agent", timeout=1 / self.room.config.tick_rate)
            # logger.info(f"AI agent {nickname} initialized using {ai_agent_file_name}")

        except ImportError as e:
            logger.error(f"Failed to import AI agent for {nickname}: {e}")
            raise e
        except Exception as e:
            logger.error(f"Failed to import AI agent for {nickname}: {e}")
            raise e

        self.agent.delivery_zone = self.game.delivery_zone.to_dict()

        self.running = True
        # logger.debug(f"AI client {nickname} started")

    def update_state(self, state_data):
        """Update the state from the game"""
        # Extract the actual state data from the nested structure
        if "type" in state_data and state_data["type"] == "state" and "data" in state_data:
            # Extract data from the nested structure
            state_data = state_data["data"]

        # Initialize collections if they don't exist yet
        if not hasattr(self.agent, "all_trains") or self.agent.all_trains is None:
            self.agent.all_trains = {}
        if not hasattr(self.agent, "passengers") or self.agent.passengers is None:
            self.agent.passengers = []
        if not hasattr(self.agent, "delivery_zone") or self.agent.delivery_zone is None:
            self.agent.delivery_zone = []
        if not hasattr(self.agent, "cell_size") or self.agent.cell_size is None:
            self.agent.cell_size = None
        if not hasattr(self.agent, "game_width") or self.agent.game_width is None:
            self.agent.game_width = None
        if not hasattr(self.agent, "game_height") or self.agent.game_height is None:
            self.agent.game_height = None
        if not hasattr(self.agent, "best_scores") or self.agent.best_scores is None:
            self.agent.best_scores = []

        # Update trains if present in the state data
        if "trains" in state_data:
            # Update only the modified trains
            for nickname, train_data in state_data["trains"].items():
                # If the train doesn't exist yet in all_trains, create it
                if nickname not in self.agent.all_trains:
                    self.agent.all_trains[nickname] = {}
                    
                # Update the train data with the new values
                for key, value in train_data.items():
                    self.agent.all_trains[nickname][key] = value

        # Update passengers if present
        if "passengers" in state_data:
            self.agent.passengers = state_data["passengers"]

        # Update delivery zone if present
        if "delivery_zone" in state_data:
            self.agent.delivery_zone = state_data["delivery_zone"]

        # Update size if present
        if "size" in state_data:
            self.agent.game_width = state_data["size"]["game_width"]
            self.agent.game_height = state_data["size"]["game_height"]

        # Update cell size if present
        if "cell_size" in state_data:
            self.agent.cell_size = state_data["cell_size"]

        # Update best scores if present
        if "best_scores" in state_data:
            self.agent.best_scores = state_data["best_scores"]

        # Update remaining time if present
        if "remaining_time" in state_data:
            if not hasattr(self.agent, "remaining_time"):
                self.agent.remaining_time = 0
            self.agent.remaining_time = state_data["remaining_time"]

        # Update other properties
        self.in_waiting_room = not self.game.game_started

        # Update agent state only if train is alive and game contains train
        if not self.is_dead and self.game.contains_train(self.nickname):
            try:
                # Call get_move() directly without thread overhead (server AI is trusted)
                self._fast_update_agent()
            except Exception as e:
                logger.error(f"Error during agent update for {self.nickname}: {e}")

    def _fast_update_agent(self):
        """Optimized agent update with timeout protection for student code.
        
        Uses signal.alarm for timeout (more efficient than thread creation).
        Falls back to direct call if signal is not available (Windows).
        """
        import signal
        from common import move
        
        class TimeoutError(Exception):
            pass
        
        def timeout_handler(signum, frame):
            raise TimeoutError()
        
        new_direction = None
        timeout_seconds = 1  # Same as BaseAgent timeout
        
        try:
            # Set up signal-based timeout (Unix only, but more efficient)
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
            
            try:
                new_direction = self.agent.get_move()
            finally:
                signal.alarm(0)  # Cancel the alarm
                signal.signal(signal.SIGALRM, old_handler)  # Restore handler
                
        except TimeoutError:
            logger.error(f"Agent {self.nickname} too slow. Execution exceeded timeout limit of {timeout_seconds}s")
            return
        except AttributeError:
            # signal.SIGALRM not available (Windows) - call directly without timeout
            try:
                new_direction = self.agent.get_move()
            except Exception as e:
                logger.error(f"Error in get_move() for {self.nickname}: {e}")
                return
        except Exception as e:
            logger.error(f"Error in get_move() for {self.nickname}: {e}")
            return
        
        if new_direction is None:
            return
        
        # Check if it's a valid Move enum
        if not isinstance(new_direction, move.Move):
            return
        
        if new_direction == move.Move.DROP:
            self.network.send_drop_wagon_request()
            return
        
        if new_direction != self.agent.all_trains[self.nickname]["direction"]:
            self.network.send_direction_change(new_direction.value)

    def stop(self):
        """Stop the AI client"""
        # logger.debug(f"Stopping AI client {self.nickname}")
        self.running = False
