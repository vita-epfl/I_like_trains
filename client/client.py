"""
Main module for the game "I Like Trains"
"""
import pygame
import logging
import time
import threading
from network import NetworkManager
from renderer import Renderer
from event_handler import EventHandler
from game_state import GameState
from ui import UI
import sys
from agent import Agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("client")

# Constants
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5555
SCREEN_WIDTH = 500
SCREEN_HEIGHT = 360
CELL_SIZE = 20
LEADERBOARD_WIDTH = 280  # Width of the leaderboard on the right

MANUAL_SPAWN = False  # Enable manual respawn
ACTIVATE_AGENT = True  # Enable agent
MANUAL_CONTROL = True  # Enable manual control


class Client:
    """Main client class"""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        """Initialize the client"""
        self.host = host
        self.port = port

        # Initialize state variables
        self.running = True
        self.is_initialized = False
        self.in_waiting_room = True
        self.lock = threading.Lock()  # Add thread lock for synchronization

        # Game over variables
        self.game_over = False
        self.game_over_data = None
        self.final_scores = []

        # Name verification variables
        self.name_check_received = False
        self.name_check_result = False

        # Sciper verification variables
        self.sciper_check_received = False
        self.sciper_check_result = False

        # Game data
        self.agent_name = ""
        self.trains = {}
        self.passengers = []
        self.delivery_zone = {}

        self.cell_size = CELL_SIZE
        self.game_width = 200  # Initial game area width
        self.game_height = 200  # Initial game area height
        self.game_screen_padding = CELL_SIZE  # Space between game area and leaderboard
        self.leaderboard_width = LEADERBOARD_WIDTH
        self.leaderboard_height = 2*self.game_screen_padding + self.game_height

        self.leaderboard_data = []
        self.waiting_room_data = None

        # Calculate screen dimensions based on game area and leaderboard
        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT

        # Window creation flags and parameters
        self.window_needs_update = False
        self.window_update_params = {
            "width": self.screen_width,
            "height": self.screen_height
        }

        # Initialize pygame but don't create window yet
        pygame.init()
        self.screen = pygame.display.set_mode(
            (self.screen_width, self.screen_height), pygame.RESIZABLE)
        pygame.display.set_caption("I Like Trains")
        self.is_initialized = True

        # Initialize components
        self.network = NetworkManager(self, host, port)
        self.renderer = Renderer(self)
        self.event_handler = EventHandler(self, ACTIVATE_AGENT, MANUAL_CONTROL)
        self.game_state = GameState(self, ACTIVATE_AGENT)
        self.ui = UI(self)

        # Reference to the agent (will be initialized later)
        self.agent = None

    def update_game_window_size(self, width, height):
        """Schedule window size update to be done in main thread"""
        # logger.info(f"Scheduling window size update to {width}x{height}")
        with self.lock:
            self.window_needs_update = True
            self.window_update_params = {
                "width": width,
                "height": height
            }

    def handle_window_updates(self):
        """Process any pending window updates in the main thread"""
        with self.lock:
            if self.window_needs_update:
                width = self.window_update_params["width"]
                height = self.window_update_params["height"]

                # logger.info(f"Updating window size to {width}x{height}")
                try:
                    self.screen = pygame.display.set_mode(
                        (width, height), pygame.RESIZABLE)
                    pygame.display.set_caption(
                        f"I Like Trains - {self.agent_name}" if self.agent_name else "I Like Trains")
                    # logger.info(f"Window updated successfully")
                except Exception as e:
                    logger.error(f"Error updating window: {e}")

                self.window_needs_update = False

    def set_agent(self, agent):
        """Set the agent for the client"""
        self.agent = agent
        self.agent_name = agent.agent_name

    def run(self):
        logger.info("Starting client loop")
        """Main client loop"""
        # Connect to server
        if not self.network.connect():
            logger.error("Failed to connect to server")
            return

        # Create a temporary window for player name
        logger.info("Creating temporary window for player name")
        temp_width, temp_height = SCREEN_WIDTH, SCREEN_HEIGHT
        try:
            self.screen = pygame.display.set_mode((temp_width, temp_height))
            pygame.display.set_caption("I Like Trains - Login")
        except Exception as e:
            logger.error(f"Error creating login window: {e}")
            return

        # Ask player to enter their name and sciper
        player_name, player_sciper = self.ui.get_player_ids()

        # Update agent name
        self.agent.agent_name = player_name
        self.agent_name = player_name
        self.agent_sciper = player_sciper  # Store sciper for future use

        # Send agent name to server
        if not self.network.send_agent_ids(self.agent_name, self.agent_sciper):
            logger.error("Failed to send agent name to server")
            return

        # Main loop
        clock = pygame.time.Clock()
        logger.info(f"Running client loop: {self.running}")
        while self.running:
            # Handle events
            self.event_handler.handle_events()

            # Handle any pending window updates in the main thread
            self.handle_window_updates()

            # Add automatic respawn logic
            if not MANUAL_SPAWN and self.agent.is_dead and self.agent.waiting_for_respawn and not self.game_over:
                elapsed = time.time() - self.agent.death_time
                if elapsed >= self.agent.respawn_cooldown:
                    if self.in_waiting_room:
                        self.network.send_start_game_request()
                    self.network.send_spawn_request()

            # Draw the game
            self.renderer.draw_game()

            # Limit FPS
            clock.tick(60)

        # Close connection
        self.network.disconnect()
        pygame.quit()

    def handle_state_data(self, data):
        """Handle state data received from server"""
        self.game_state.handle_state_data(data)

    def handle_death(self, data):
        """Handle cooldown data received from server"""
        self.game_state.handle_death(data)

    def handle_game_status(self, data):
        """Handle game status received from server"""
        self.game_state.handle_game_status(data)

    def handle_leaderboard_data(self, data):
        """Handle leaderboard data received from server"""
        self.game_state.handle_leaderboard_data(data)

    def handle_waiting_room_data(self, data):
        """Handle waiting room data received from server"""
        self.game_state.handle_waiting_room_data(data)

    def handle_drop_wagon_success(self, data):
        """Handle successful wagon drop response from server"""
        self.game_state.handle_drop_wagon_success(data)

    def handle_game_over(self, data):
        """Handle game over data received from server"""
        self.game_state.handle_game_over(data)

    def handle_initial_state(self, data):
        """Handle initial state message from server"""
        logger.info("Received initial state from server")

        # Store game lifetime and start time
        # Default to 60 seconds if not provided
        self.game_life_time = data.get("game_life_time", 60)
        self.game_start_time = time.time()  # Use client's time for consistency

        logger.info(f"Game lifetime set to {self.game_life_time} seconds")

    def get_remaining_time(self):
        """Calculate remaining game time in seconds"""
        if not hasattr(self, 'game_life_time') or not hasattr(self, 'game_start_time'):
            return None

        elapsed = time.time() - self.game_start_time
        remaining = max(0, self.game_life_time - elapsed)
        return remaining


def main():
    """Main function"""
    # Check if an IP address was provided as an argument
    host = DEFAULT_HOST
    if len(sys.argv) > 1:
        host = sys.argv[1]

    # Check if a port was provided as an argument
    port = DEFAULT_PORT
    if len(sys.argv) > 2:
        port = int(sys.argv[2])

    logger.info(f"Connecting to server: {host}")

    # Create the client
    client = Client(host, port)

    # Create the agent with a temporary name (will be replaced by user input)
    agent = Agent("", client.network)

    # Set the agent for the client
    client.set_agent(agent)

    # Start the client
    try:
        client.run()
    except KeyboardInterrupt:
        logger.info("Client stopped by user")
    except Exception as e:
        logger.error(f"Error during client execution: {e}")
    finally:
        logger.info("Client closed")


if __name__ == "__main__":
    main()
