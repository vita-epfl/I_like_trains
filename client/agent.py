import random
import logging
from base_agent import BaseAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("game_debug.log"), logging.StreamHandler()],
)

BASE_DIRECTIONS = [
    (0, -1),  # Up
    (1, 0),  # Right
    (0, 1),  # Down
    (-1, 0),  # Left
]


class Agent(BaseAgent):
    def __init__(
        self,
        agent_name: str,
        network: NetworkManager,
        logger: str = "client.agent",
        is_dead: bool = True,
    ):
        """
        Initialize the agent
        Args:
            agent_name (str): The name of the agent
            network (NetworkManager): The network object to handle communication
            logger (str): The logger name
            is_dead (bool): Whether the agent is dead
        """
        super().__init__(agent_name, network, logger, is_dead)

        self.logger.info(f"Agent {self.agent_name} initialized")

    # =========================================
    # Required method
    # =========================================

    def get_direction(self):
        """
        This method is regularly called by the client to get the next direction of the train.
        """
        return random.choice(BASE_DIRECTIONS)

    # =========================================
    # Method ideas (can be removed or completed)
    # =========================================

    def will_hit_wall(self, position: tuple, direction: tuple):
        """
        Check if the next position will hit a wall
        Args:
            position (tuple): The current position of the train
            direction (tuple): The direction of the train
        Returns:
            bool: True if the next position will hit a wall, False otherwise
        """
        return

    def will_hit_train_or_wagon(self, position: tuple, direction: tuple):
        """Check if the direction leads to a collision with a train or wagon"""
        return

    def get_target_position(self, current_position: tuple):
        """Find the adapted target and return its position"""
        return

    def get_direction_to_target(
        self, current_position: tuple, target_position: tuple, valid_directions: list
    ):
        """Determine the best direction among the valid ones to reach the target the fastest"""
        return

    def is_opposite_direction(self, new_direction: tuple):
        """Check if the new direction is opposite to the current direction"""
        return
