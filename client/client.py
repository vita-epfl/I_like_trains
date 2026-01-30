from __future__ import annotations

import pygame
import logging
import time
import threading
import sys
import importlib
import random
from typing import Any

from client.network import NetworkManager
from client.renderer import Renderer
from client.event_handler import EventHandler
from client.game_state import GameState

from common.config import Config
from common.client_config import ClientConfig, GameMode
from common.base_agent import BaseAgent
from common.constants import REFERENCE_TICK_RATE


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("client")


class Client:
    """Main client class"""

    def __init__(self, config: Config) -> None:
        """Initialize the client"""
        self.config: ClientConfig = config.client
        self.game_mode: GameMode = self.config.game_mode

        # If we launch an observer, we want the host to be local_host, otherwise
        if self.game_mode == GameMode.OBSERVER:
            host = "localhost"
            logger.info("Observer mode: connecting to localhost")
        else:
            host = self.config.host
            logger.info(f"Client mode: connecting to {host}")

        # Initialize state variables
        self.running: bool = True
        self.is_dead: bool = False
        self.waiting_for_respawn: bool = False
        self.death_time: float = 0
        self.respawn_cooldown: float = 0
        self.last_spawn_request_time: float = 0
        self.is_initialized: bool = False
        self.in_waiting_room: bool = True
        self.lock: threading.Lock = threading.Lock()

        # Game over variables
        self.game_over: bool = False
        self.game_over_data: dict[str, Any] | None = None
        self.best_scores: dict[str, int] = {}
        self.final_scores: list[dict[str, Any]] = []

        # Name verification variables
        self.name_check_received: bool = False
        self.name_check_result: bool = False

        # Sciper verification variables
        self.sciper_check_received: bool = False
        self.sciper_check_result: bool = False

        # Game data
        self.trains: dict[str, dict[str, Any]] = {}
        self.passengers: list[dict[str, Any]] = []
        self.delivery_zone: dict[str, Any] = {}

        # TODO(alok): delete self.cell_size, use self.config.cell_size everywhere
        self.cell_size: int = 0
        self.game_width: int = 200  # Initial game area width
        self.game_height: int = 200  # Initial game area height

        # Space between game area and leaderboard
        self.game_screen_padding: int = 20
        self.leaderboard_width: int = self.config.leaderboard_width
        self.leaderboard_height: int = 2 * self.game_screen_padding + self.game_height

        self.leaderboard_data: list[dict[str, Any]] = []
        self.waiting_room_data: dict[str, Any] | None = None

        self.screen_width: int = 380
        self.screen_height: int = 240 

        self.nb_players: int = 0

        # Window creation flags and parameters
        self.window_needs_update: bool = False
        self.window_update_params: dict[str, int] = {
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
        self.network: NetworkManager = NetworkManager(self, host, self.config.port)
        self.renderer: Renderer = Renderer(self)

        self.event_handler: EventHandler = EventHandler(self, self.game_mode)
        self.game_state: GameState = GameState(self, self.game_mode)

        # Initialize agent based on game mode
        self.agent: BaseAgent | None = None

        # Set nickname based on game mode
        self.nickname: str = ""
        if self.game_mode == GameMode.MANUAL:
            self.nickname = self.config.manual.nickname
            self.sciper = self.config.sciper
        elif self.game_mode == GameMode.AGENT:
            self.nickname = self.config.agent.nickname
            self.sciper = self.config.sciper
        elif self.game_mode == GameMode.OBSERVER:
            self.nickname = ""
            self.sciper = self.config.sciper

        if self.config.add_suffix_to_nickname:
            # Add random suffix
            self.nickname += f"_{random.randint(0, 9999)}"

        if self.game_mode != GameMode.OBSERVER:
            logger.debug("Initializing agent")
            agent_info = self.config.agent
            if agent_info and hasattr(agent_info, "agent_file_name"):
                logger.info(f"Loading agent: {agent_info.agent_file_name}")
                agent_file_name = agent_info.agent_file_name
                if agent_file_name.endswith(".py"):
                    # Remove .py extension
                    agent_file_name = agent_file_name[:-3]

                # Construct the module path correctly
                module_path = f"common.agents.{agent_file_name}"
                logger.info(f"Importing module: {module_path}")

                # Add parent directory to Python path to allow importing agents package
                module = importlib.import_module(module_path)
                self.agent = module.Agent(self.nickname, self.network, timeout=1/REFERENCE_TICK_RATE)

        self.ping_response_received: bool = False
        self.server_disconnected: bool = False

    def update_game_window_size(self, width: int | None = None, height: int | None = None) -> None:
        """Schedule window size update to be done in main thread"""
        with self.lock:
            if (width is not None):
                self.window_update_params["width"] = width
                self.window_needs_update = True
            if (height is not None):
                self.window_update_params["height"] = height
                self.window_needs_update = True

    def handle_window_updates(self) -> None:
        """Process any pending window updates in the main thread"""
        with self.lock:
            if self.window_needs_update:
                width = self.window_update_params["width"]
                height = self.window_update_params["height"]

                self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                pygame.display.set_caption(f"I Like Trains - {self.game_mode.value}")

                self.window_needs_update = False

    def run(self) -> None:
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
                        logger.info(f"Connected to server at {self.config.host}:{self.config.port}")
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
                        self.screen_width // 2 - text.get_width() // 2,
                        self.screen_height // 2 - text.get_height() // 2,
                    ),
                )
                pygame.display.flip()
                pygame.time.wait(3000)  # Show error for 3 seconds
            pygame.quit()
            return

        if not self.network.send_agent_ids(
            self.nickname, self.sciper, self.game_mode.value
        ):
            logger.error("Failed to send agent ids to server")
            return

        # Main loop
        logger.info(f"Running client loop: {self.running}")
        clock = pygame.time.Clock()
        while self.running:
            self.update()
            clock.tick(REFERENCE_TICK_RATE)

        # Close connection
        self.network.disconnect()
        pygame.quit()

    def update(self) -> None:
        """Update client state"""
        # Handle events
        self.event_handler.handle_events()
        self.handle_window_updates()

        # Add automatic respawn logic
        if (
            not self.config.manual_spawn
            and self.is_dead
            and self.waiting_for_respawn
            and not self.game_over
        ):
            elapsed = time.time() - self.death_time
            current_time = time.time()
            # Only send spawn request if cooldown has passed AND at least 1 second since last request
            if elapsed >= self.respawn_cooldown and current_time - self.last_spawn_request_time >= 1.0:
                logger.debug("Sending spawn request.")
                self.network.send_spawn_request()
                self.last_spawn_request_time = current_time

        self.renderer.draw_game()

    def handle_state_data(self, data: dict[str, Any]) -> None:
        """Handle state data received from server"""
        self.game_state.handle_state_data(data)

    def handle_death(self, data: dict[str, Any]) -> None:
        """Handle cooldown data received from server"""
        self.game_state.handle_death(data)

    def handle_game_status(self, data: dict[str, Any]) -> None:
        """Handle game status received from server"""
        self.game_state.handle_game_status(data)

    def handle_leaderboard_data(self, data: Any) -> None:
        """Handle leaderboard data received from server"""
        self.game_state.handle_leaderboard_data(data)

    def handle_waiting_room_data(self, data: dict[str, Any]) -> None:
        """Handle waiting room data received from server"""
        self.game_state.handle_waiting_room_data(data)

    def handle_game_over(self, data: dict[str, Any]) -> None:
        """Handle game over data received from server"""
        self.game_state.handle_game_over(data)

    def handle_initial_state(self, data: dict[str, Any]) -> None:
        """Handle initial state message from server"""
        logger.info("Received initial state from server")

        # Store game lifetime and start time
        self.game_life_time = data.get(
            "game_life_time", 60
        )  # Default to 60 seconds if not provided
        self.game_start_time = time.time()  # Use client's time for consistency

        logger.info(f"Game lifetime set to {self.game_life_time} seconds")

    def handle_server_disconnection(self) -> None:
        """Handle server disconnection gracefully"""
        logger.warning("Server disconnected, shutting down client...")
        self.server_disconnected = True
        self.running = False

        # Afficher un message à l'utilisateur si pygame est initialisé
        if hasattr(self, "renderer") and self.renderer and pygame.display.get_init():
            font = pygame.font.SysFont("Arial", 24)
            text = font.render(
                "Server disconnected. Press any key to exit.", True, (255, 0, 0)
            )
            text_rect = text.get_rect(
                center=(
                    self.config.screen_width // 2,
                    self.config.screen_height // 2,
                )
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

        # Fermer proprement
        self.cleanup()

    def cleanup(self) -> None:
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
