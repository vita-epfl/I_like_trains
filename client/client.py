import pygame
import logging
import time
import threading
import sys
from network import NetworkManager
from renderer import Renderer
from event_handler import EventHandler
from game_state import GameState
from agent import Agent
import json


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("client")

# Constants, imported from config.json
with open("config.json", "r") as f:
    try:
        config = json.load(f)
    except json.decoder.JSONDecodeError as e:
        print("Failed to parse config.json, check your changes.", file=sys.stderr)
        raise e

DEFAULT_HOST = "localhost"


class Client:
    """Main client class"""

    def __init__(self, host=DEFAULT_HOST, port=config["default_port"]):
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

        self.cell_size = config["cell_size"]
        self.game_width = 200  # Initial game area width
        self.game_height = 200  # Initial game area height
        self.game_screen_padding = config[
            "cell_size"
        ]  # Space between game area and leaderboard
        self.leaderboard_width = config["leaderboard_width"]
        self.leaderboard_height = 2 * self.game_screen_padding + self.game_height

        self.leaderboard_data = []
        self.waiting_room_data = None

        # Calculate screen dimensions based on game area and leaderboard
        self.screen_width = config["screen_width"]
        self.screen_height = config["screen_height"]

        # Window creation flags and parameters
        self.window_needs_update = False
        self.window_update_params = {
            "width": self.screen_width,
            "height": self.screen_height,
        }

        # Initialize pygame but don't create window yet
        pygame.init()
        self.screen = pygame.display.set_mode(
            (self.screen_width, self.screen_height), pygame.RESIZABLE
        )
        pygame.display.set_caption("I Like Trains")
        self.is_initialized = True

        # Initialize components
        self.network = NetworkManager(self, host, port)
        self.renderer = Renderer(self)
        self.event_handler = EventHandler(self, config["control_mode"])
        self.game_state = GameState(self, config["control_mode"])

        # Reference to the agent (will be initialized later)
        self.agent = None
        self.ping_response_received = False  # Added for connection verification
        self.server_disconnected = False

    def update_game_window_size(self, width, height):
        """Schedule window size update to be done in main thread"""
        with self.lock:
            self.window_needs_update = True
            self.window_update_params = {"width": width, "height": height}

    def handle_window_updates(self):
        """Process any pending window updates in the main thread"""
        with self.lock:
            if self.window_needs_update:
                width = self.window_update_params["width"]
                height = self.window_update_params["height"]

                try:
                    self.screen = pygame.display.set_mode(
                        (width, height), pygame.RESIZABLE
                    )
                    pygame.display.set_caption(
                        f"I Like Trains - {self.agent_name}"
                        if self.agent_name
                        else "I Like Trains"
                    )
                except Exception as e:
                    logger.error(f"Error updating window: {e}")

                self.window_needs_update = False

    def set_agent(self, agent):
        """Set the agent for the client"""
        self.agent = agent
        self.agent_name = agent.agent_name

    def run(self):
        """Main client loop"""
        logger.info("Starting client loop")
        # Connect to server with timeout
        connection_timeout = 5  # 5 seconds timeout
        connection_start_time = time.time()

        connection_successful = False
        while time.time() - connection_start_time < connection_timeout:
            try:
                if self.network.connect():
                    # Verify connection by attempting to receive data
                    if self.network.verify_connection():
                        logger.info("Connected to server successfully")
                        connection_successful = True
                        break
                    else:
                        logger.warning(
                            "Connection reported success but failed verification"
                        )
                time.sleep(0.5)  # Small delay between connection attempts
            except Exception as e:
                logger.error(f"Connection attempt failed: {e}")
                time.sleep(0.5)

        if not connection_successful:
            logger.error(
                f"Failed to connect to server after {connection_timeout} seconds timeout"
            )
            # Show error message to user
            if self.screen:
                font = pygame.font.Font(None, 26)
                text = font.render(
                    "Connection to server failed. Check port and server status.",
                    True,
                    (255, 0, 0),
                )
                self.screen.fill((0, 0, 0))
                self.screen.blit(
                    text,
                    (
                        config["screen_width"] // 2 - text.get_width() // 2,
                        config["screen_height"] // 2 - text.get_height() // 2,
                    ),
                )
                pygame.display.flip()
                pygame.time.wait(3000)  # Show error for 3 seconds
            pygame.quit()
            return

        # Create a temporary window for player name
        temp_width, temp_height = config["screen_width"], config["screen_height"]
        try:
            self.screen = pygame.display.set_mode((temp_width, temp_height))
            pygame.display.set_caption("I Like Trains - Login")
        except Exception as e:
            logger.error(f"Error creating login window: {e}")
            return

        # Get player name and sciper from config
        player_sciper = config["sciper"]
        player_name = config["train_name"]

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
            if (
                not config["manual_spawn"]
                and self.agent.is_dead
                and self.agent.waiting_for_respawn
                and not self.game_over
            ):
                elapsed = time.time() - self.agent.death_time
                if elapsed >= self.agent.respawn_cooldown:
                    self.network.send_spawn_request()

            if self.in_waiting_room:
                self.network.send_start_game_request()

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
        self.game_life_time = data.get(
            "game_life_time", 60
        )  # Default to 60 seconds if not provided
        self.game_start_time = time.time()  # Use client's time for consistency

        logger.info(f"Game lifetime set to {self.game_life_time} seconds")

    def get_remaining_time(self):
        """Calculate remaining game time in seconds"""
        if not hasattr(self, "game_life_time") or not hasattr(self, "game_start_time"):
            return None

        elapsed = time.time() - self.game_start_time
        remaining = max(0, self.game_life_time - elapsed)

        return remaining

    def handle_server_disconnection(self):
        """Handle server disconnection gracefully"""
        logger.warning("Server disconnected, shutting down client...")
        self.server_disconnected = True
        self.running = False

        # Afficher un message à l'utilisateur si pygame est initialisé
        if hasattr(self, "renderer") and self.renderer and pygame.display.get_init():
            try:
                font = pygame.font.SysFont("Arial", 24)
                text = font.render(
                    "Server disconnected. Press any key to exit.", True, (255, 0, 0)
                )
                text_rect = text.get_rect(
                    center=(config["screen_width"] // 2, config["screen_height"] // 2)
                )
                self.renderer.screen.fill((0, 0, 0))
                self.renderer.screen.blit(text, text_rect)
                pygame.display.flip()

                # Attendre que l'utilisateur appuie sur une touche
                waiting = True
                while waiting:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT or event.type == pygame.KEYDOWN:
                            waiting = False
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error displaying disconnection message: {e}")

        # Fermer proprement
        self.cleanup()

    def cleanup(self):
        """Clean up resources before exiting"""
        logger.info("Cleaning up resources...")

        # Fermer la connexion réseau
        if hasattr(self, "network") and self.network:
            self.network.disconnect()

        # Quitter pygame
        if pygame.display.get_init():
            pygame.quit()

        # Quitter le programme
        if self.server_disconnected:
            logger.info("Exiting due to server disconnection")
            sys.exit(0)


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("main")


def main():
    """Main function"""
    # Check if an IP address was provided as an argument
    host = DEFAULT_HOST
    if len(sys.argv) > 1:
        host = sys.argv[1]

    # Check if a port was provided as an argument
    port = config["default_port"]
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
    client.run()


if __name__ == "__main__":
    main()
