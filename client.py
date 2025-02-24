import pygame
import random
import os
import importlib
import socket
import json
import threading
from agent import Agent
import logging
import sys
import platform
import time

# Default host
HOST = "localhost"

MANUAL_RESPAWN = True  # Set to False to respawn automatically
RESPAWN_COOLDOWN = 10.0  # RESPAWN COOLDOWN in seconds, checked by the server :p

# Check if an IP address has argued in argument
if len(sys.argv) > 1:
    HOST = sys.argv[1]


# Logger configuration for the customer and agent
def setup_client_logger():
    # Delete existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Configure the main logger
    logger = logging.getLogger("client")
    logger.setLevel(logging.DEBUG)

    # Ensure logs are propagated to parents
    logger.propagate = False

    # Create a handler for the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Define the format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(console_handler)

    # Also configure the agent logger
    agent_logger = logging.getLogger("client.agent")
    agent_logger.setLevel(logging.DEBUG)
    agent_logger.addHandler(console_handler)
    agent_logger.propagate = False

    return logger


# Configure the logger before creating the agent
logger = setup_client_logger()
logger.info(f"The client listens on {HOST}")


class Client:

    def __init__(self, agent_name, server_host=HOST, server_port=5555):
        self.agent_name = agent_name
        self.agent = Agent(agent_name, self.send_action, MANUAL_RESPAWN)
        self.server_host = server_host
        self.server_port = server_port

        self.running = True
        self.trains = []
        self.passengers = []

        self.grid_size = 0
        self.screen_width = 0
        self.screen_height = 0

        self.is_initialized = False  # Track initialization state

        self.init_connection()

    def init_connection(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            self.socket.sendall(self.agent_name.encode())

            # Wait for the server response to check if the name is accepted
            response = self.socket.recv(1024).decode()
            try:
                response_data = json.loads(response)
                if "error" in response_data:
                    logger.error(f"Connection error: {response_data['error']}")
                    self.socket.close()
                    pygame.quit()
                    print(f"Error: {response_data['error']}")
                    exit(1)
                elif response_data.get("status") == "ok":
                    logger.info("Connection accepted")
                    self.init_game()
            except json.JSONDecodeError as e:
                logger.error(f"Server response decoding error: {e}")
                self.socket.close()
                raise

        except ConnectionRefusedError as e:
            logger.error(
                f"Unable to connect to server {self.server_host}:{self.server_port}"
            )
            logger.error(str(e))
            raise
        except Exception as e:
            logger.error(f"An error occurred while trying to connect: {e}")
            raise

    def init_game(self):
        """Initialize pygame only if it hasn't been initialized yet."""
        if not self.is_initialized:
            try:
                # Check if DISPLAY is set (Linux/macOS) or running on Windows
                if "DISPLAY" in os.environ or platform.system() == "Windows":
                    pygame.init()
                    self.screen = pygame.display.set_mode(
                        (self.screen_width, self.screen_height)
                    )
                    pygame.display.set_caption(f"Train Game - {self.agent_name}")
                else:
                    # Use a headless video driver if no display is available
                    os.environ["SDL_VIDEODRIVER"] = "dummy"
                    pygame.init()
                    pygame.display.set_mode((1, 1))  # Create a dummy surface
                    logger.warning("No display found, running in headless mode")
                self.clock = pygame.time.Clock()
                self.is_initialized = True
            except pygame.error as e:
                logger.error(f"Failed to initialize pygame: {e}")
                self.running = False

    def update_agent(self):
        """Met à jour l'état de l'agent."""
        start_time = time.time()

        self.agent.all_trains = self.trains
        self.agent.all_passengers = self.passengers
        self.agent.grid_size = self.grid_size
        self.agent.screen_width = self.screen_width
        self.agent.screen_height = self.screen_height

        if (
            self.agent_name not in self.trains
            and not self.agent.waiting_for_respawn
            and not self.agent.is_dead
        ):
            self.agent.logger.debug(
                f"Train {self.agent_name} not in the list of trains and not dead"
            )
            self.agent.is_dead = True
            self.agent.death_time = time.time()
            self.agent.respawn_cooldown = RESPAWN_COOLDOWN

        if (
            self.agent_name not in self.trains
            and self.agent.is_dead
            and not self.agent.waiting_for_respawn
        ):
            elapsed = time.time() - self.agent.death_time
            remaining_time = max(0, self.agent.respawn_cooldown - elapsed)

            if remaining_time == 0:
                if MANUAL_RESPAWN:
                    keys = pygame.key.get_pressed()
                    if keys[pygame.K_SPACE]:
                        self.agent.logger.info(f"Train {self.agent_name} requests a respawn")
                        self.agent.is_dead = False
                        self.agent.waiting_for_respawn = True
                        self.send_action({"action": "respawn"})
                else:
                    self.agent.logger.info(f"Train {self.agent_name} requests a respawn")
                    self.agent.is_dead = False
                    self.agent.waiting_for_respawn = True
                    self.send_action({"action": "respawn"})

            return

        if not self.agent.is_dead and self.agent_name in self.trains:
            self.agent.waiting_for_respawn = False
            decision_start = time.time()
            direction = self.agent.get_valid_direction(self.grid_size, self.screen_width, self.screen_height)
            decision_time = time.time() - decision_start
            if decision_time > 0.01:
                self.agent.logger.warning(f"Decision making took {decision_time*1000:.2f}ms")

            send_start = time.time()
            self.send_action(direction)
            send_time = time.time() - send_start
            if send_time > 0.01:
                self.agent.logger.warning(f"Action sending took {send_time*1000:.2f}ms")

            total_time = time.time() - start_time
            if total_time > 0.05:
                self.agent.logger.warning(f"Total update took {total_time*1000:.2f}ms")

    def receive_game_state(self):
        buffer = ""
        self.socket.settimeout(None)  # No timeout for reception
        while self.running:
            try:
                # Receive the data
                data = self.socket.recv(4096).decode()
                if not data:
                    break

                # Add to the buffer
                buffer += data

                # Process each complete message (delimited by \n)
                messages = buffer.split("\n")
                # Keep the last incomplete message in the buffer
                buffer = messages[-1]

                # Process only the last complete message
                if len(messages) > 1:
                    try:
                        state = json.loads(
                            messages[-2]
                        )  # Take the last complete message

                        # Check if the state is a dictionary
                        if isinstance(state, dict):
                            # Update the game data
                            if "trains" in state:
                                self.trains = state["trains"]
                            else:
                                self.trains = {}
                                logger.warning(
                                    "Received game state without 'trains' key"
                                )
                            if "passengers" in state:
                                self.passengers = state["passengers"]
                            else:
                                self.passengers = []
                                logger.warning(
                                    "Received game state without 'passengers' key"
                                )
                            if "grid_size" in state:
                                self.grid_size = state["grid_size"]
                            else:
                                self.grid_size = 20  # Valeur par défaut
                                logger.warning(
                                    "Received game state without 'grid_size' key, using default value"
                                )
                            self.screen_width = state.get("screen_width", 0)
                            self.screen_height = state.get("screen_height", 0)

                            # Update the agent if the train is alive
                            self.update_agent()
                        else:
                            logger.error("Received game state is not a dictionary")

                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON: {e}")

            except socket.timeout:
                continue  # Continue the loop in case of timeout
            except Exception as e:
                logger.error(f"Error in receive_game_state: {e}")
                break

        logger.warning("Stopped receiving game state")
        self.running = False

    def send_action(self, direction):
        try:
            # If it's a dictionary (case of respawn), send it directly
            if isinstance(direction, dict):
                action = direction
                # logger.debug(f"Sending action: {action}")
            else:
                action = {"action": "direction", "direction": list(direction)}
                # logger.debug(f"Sending action: {action}")
            self.socket.sendall((json.dumps(action) + "\n").encode())
        except Exception as e:
            logger.error(f"Error sending action: {e}")

    def run(self):
        threading.Thread(target=self.receive_game_state).start()

        while self.running:
            # Process events first
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                # Ignore window active/inactive events
                elif event.type in (
                    pygame.WINDOWFOCUSLOST,
                    pygame.WINDOWMOVED,
                    pygame.WINDOWENTER,
                    pygame.WINDOWLEAVE,
                ):
                    continue

            # Update the screen size if necessary
            if (
                self.screen_width != self.screen.get_width()
                or self.screen_height != self.screen.get_height()
            ):
                self.screen = pygame.display.set_mode(
                    (self.screen_width, self.screen_height)
                )

            # Call the game rendering via the agent
            self.agent.draw_gui(self.screen, self.grid_size)

            # Small delay to avoid excessive CPU usage
            pygame.time.delay(10)

        logger.warning("Client stopped")
        self.socket.close()
        pygame.quit()


if __name__ == "__main__":
    while True:
        agent_name = input("Enter agent name: ")
        if agent_name:
            break
        else:
            logger.warning("Agent name cannot be empty")
    client = Client(agent_name, HOST)
    client.run()
