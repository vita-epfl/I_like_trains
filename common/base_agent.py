import logging
import threading
import ctypes
from client.network import NetworkManager
from common import move
from common.constants import REFERENCE_TICK_RATE


def _terminate_thread(thread):
    """Terminate a thread forcefully.
    
    Args:
        thread: The thread to terminate
    """
    if not thread.is_alive():
        return
        
    # Get thread identifier
    tid = ctypes.c_long(thread.ident)
    
    # Raise exception in the thread
    exc = ctypes.py_object(SystemExit)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, exc)
    
    if res == 0:
        # Thread ID not found
        raise ValueError("Invalid thread ID")
    elif res > 1:
        # If multiple threads were affected, clean up and raise error
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


class BaseAgent:
    """Base class for all agents, enforcing the implementation of get_move()."""

    def __init__(
        self, nickname: str, network: NetworkManager, logger: str = "client.agent", timeout: float = 1/REFERENCE_TICK_RATE
    ):
        """
        Initialize the base agent. Not supposed to be modified.

        Args:
            nickname (str): The name of the agent
            network (NetworkManager): The network object to handle communication
            logger (str): The logger name

        Attributes:
            cell_size (int): The size of a cell in pixels
            game_width (int): The width of the game in cells
            game_height (int): The height of the game in cells
            all_trains (dict): Dictionary of all trains in the game
            passengers (list): List of passengers in the game
            delivery_zone (list): List of delivery zones in the game
        """
        self.logger = logging.getLogger(logger)
        if logger == "client.agent":
            self.logger.setLevel(logging.DEBUG)
        self.nickname = nickname
        self.network = network
        # self.timeout = timeout
        self.timeout = 1  # Exceptionally overriding it to 1 second

        # Game parameters, regularly updated by the client in handle_state_data() (see game_state.py)
        self.cell_size = None
        self.game_width = None
        self.game_height = None
        self.all_trains = None
        self.passengers = None
        self.delivery_zone = None
        self.best_scores = None

    def _run_get_move(self):
        """
        Wrapper method to call get_move() in a separate thread.
        Stores the result in self._move_result.
        """
        self._move_result = self.get_move()

    def get_move(self):
        """
        Abstract method to be implemented by subclasses.
        Must return a valid move.Move.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def update_agent(self):
        """
        Regularly called by the client to send the new direction to the server. Not supposed to be modified.

        Returning from this method without doing anything will cause the train to continue moving forward.
        """
        # Create a thread dedicated to get_move() that we can control directly
        worker_thread = threading.Thread(target=self._run_get_move)
        worker_thread.daemon = True  # The thread will close with the main program
        
        # Variable to store the result
        self._move_result = None
        
        # Start the thread
        worker_thread.start()
        
        # Wait for the thread to finish or timeout
        worker_thread.join(self.timeout)
        
        # If the thread is still running after the timeout
        if worker_thread.is_alive():
            # Terminate it forcefully
            try:
                _terminate_thread(worker_thread)
                error_msg = f"Agent {self.nickname} too slow. Execution exceeded timeout limit of {round(self.timeout, 3)}s"
                self.logger.error(error_msg)
                return
            except Exception as e:
                self.logger.error(f"Failed to terminate agent thread: {e}")
                return
        
        # If we arrive here, the thread has finished normally
        if self._move_result is None:
            # get_move() has finished but did not return a valid result
            return
        
        new_direction = self._move_result
            
        # Check if it's a valid Move enum
        if not isinstance(new_direction, move.Move):
            move_names = [f'<Move.{name}>' for name in move.Move.__members__]
            self.logger.error(f"get_move() did not return a valid move. Got: {new_direction}. Expected one of: [{', '.join(move_names)}]")

        if new_direction == move.Move.DROP:
            self.network.send_drop_wagon_request()
            return

        if new_direction != self.all_trains[self.nickname]["direction"]:
            self.network.send_direction_change(new_direction.value)
