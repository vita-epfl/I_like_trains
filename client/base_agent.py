import logging
import time
from client.network import NetworkManager
from common import move

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("game_debug.log"), logging.StreamHandler()],
)


class BaseAgent:
    """Base class for all agents, enforcing the implementation of get_move()."""

    def __init__(
        self,
        agent_name: str,
        network: NetworkManager,
        logger: str = "client.agent",
        is_dead: bool = True,
    ):
        """
        Initialize the base agent. Not supposed to be modified.

        Args:
            agent_name (str): The name of the agent
            network (NetworkManager): The network object to handle communication
            logger (str): The logger name
            is_dead (bool): Whether the agent is dead

        Attributes:
            death_time (float): The time when the agent last died
            respawn_cooldown (float): The cooldown time before respawning
            is_dead (bool): Whether the agent is dead
            waiting_for_respawn (bool): Whether the agent is waiting for respawn
            cell_size (int): The size of a cell in pixels
            game_width (int): The width of the game in cells
            game_height (int): The height of the game in cells
            all_trains (dict): Dictionary of all trains in the game
            passengers (list): List of passengers in the game
            delivery_zone (list): List of delivery zones in the game
        """
        self.logger = logging.getLogger(logger)
        self.agent_name = agent_name
        self.network = network

        self.death_time = time.time()
        self.respawn_cooldown = 0
        self.is_dead = is_dead
        self.waiting_for_respawn = True

        # Game parameters, regularly updated by the client in handle_state_data() (see game_state.py)
        self.cell_size = None
        self.game_width = None
        self.game_height = None
        self.all_trains = None
        self.passengers = None
        self.delivery_zone = None

    def get_move(self):
        """
        Abstract method to be implemented by subclasses.
        Must return a valid move.Move.
        """
        pass

    def update_agent(self):
        """
        Regularly called by the client to send the new direction to the server. Not supposed to be modified.
        Example of how to access the elements of the game state:
        """
        if not self.is_dead:
            new_direction = self.get_move()
            if new_direction not in move.Move:
                # Not doing anything is akin to keep moving forward
                return

            if new_direction == move.Move.DROP:
                self.network.send_drop_wagon_request()

            if new_direction != self.all_trains[self.agent_name]["direction"]:
                self.network.send_direction_change(new_direction)
