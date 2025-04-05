"""
Game class for the game "I Like Trains"
"""

import random
import threading
import time

from common.server_config import ServerConfig
from server.train import Train
from server.passenger import Passenger
import logging
from server.delivery_zone import DeliveryZone


# Use the logger configured in server.py
logger = logging.getLogger("server.game")

ORIGINAL_GAME_WIDTH = 400
ORIGINAL_GAME_HEIGHT = 400

ORIGINAL_GRID_NB = 20

TRAINS_PASSENGER_RATIO = 1.0  # Number of trains per passenger

GAME_SIZE_INCREMENT_RATIO = (
    0.05  # Increment per train, the bigger the number, the bigger the screen grows
)
CELL_SIZE = int(ORIGINAL_GAME_WIDTH / ORIGINAL_GRID_NB)
GAME_SIZE_INCREMENT = int(
    ((ORIGINAL_GAME_WIDTH + ORIGINAL_GAME_HEIGHT) / 2) * GAME_SIZE_INCREMENT_RATIO
)  # Increment per train

SPAWN_SAFE_ZONE = 3
SAFE_PADDING = 3

# Constant for wagon delivery cooldown time (in seconds)
DELIVERY_COOLDOWN_TIME = 0.1  # Adjust this value to control delivery speed


def generate_random_non_blue_color():
    """Generate a random RGB color avoiding blue nuances"""
    while True:
        r = random.randint(100, 230)  # Lighter for the trains
        g = random.randint(100, 230)
        b = random.randint(0, 150)  # Limit the blue

        # If it's not a blue nuance (more red or green than blue)
        if r > b + 50 or g > b + 50:
            return (r, g, b)


class Game:
    # TODO(alok): remove nb_players and use config.players_per_room
    def __init__(self, config: ServerConfig, send_cooldown_notification, nb_players):
        self.config = config
        self.send_cooldown_notification = send_cooldown_notification
        self.game_width = ORIGINAL_GAME_WIDTH
        self.game_height = ORIGINAL_GAME_HEIGHT
        self.new_game_width = self.game_width
        self.new_game_height = self.game_height
        self.cell_size = CELL_SIZE
        self.running = True
        self.delivery_zone = DeliveryZone(
            self.game_width, self.game_height, self.cell_size, nb_players
        )
        self.trains = {}
        self.ai_clients = {}
        self.best_scores = {}
        self.train_colors = {}  # {agent_name: (train_color, wagon_color)}
        self.passengers = []
        self.desired_passengers = 0
        self.dead_trains = {}  # {agent_name: death_time}
        self.lock = threading.Lock()
        self.last_update = time.time()
        self.game_started = False  # Track if game has started
        # Dictionary to track last delivery time for each train
        self.last_delivery_times = {}  # {agent_name: last_delivery_time}
        # Dirty flags for the game
        self._dirty = {
            "trains": True,
            "size": True,
            "cell_size": True,
            "passengers": True,
            "delivery_zone": True,
        }
        logger.info(f"Game initialized with tick rate: {self.config.tick_rate}")

    def get_state(self):
        """Return game state with only modified data"""
        state = {}

        # Add game dimensions if modified
        if self._dirty["size"]:
            state["size"] = {
                "game_width": self.game_width,
                "game_height": self.game_height,
            }
            self._dirty["size"] = False

        # Add grid size if modified
        if self._dirty["cell_size"]:
            state["cell_size"] = self.cell_size
            self._dirty["cell_size"] = False

        # Add passengers if modified
        if self._dirty["passengers"]:
            state["passengers"] = [p.to_dict() for p in self.passengers]
            self._dirty["passengers"] = False

        # Add modified trains
        trains_data = {}
        for name, train in self.trains.items():
            train_data = train.to_dict()
            if train_data:  # Only add if data has changed
                trains_data[name] = train_data

        # Add delivery zone if modified
        if self._dirty["delivery_zone"]:
            state["delivery_zone"] = self.delivery_zone.to_dict()
            self._dirty["delivery_zone"] = False

        if trains_data:
            state["trains"] = trains_data

        return state

    def run(self):
        logger.info("Game loop started")
        while self.running:
            self.update()
            time.sleep(1 / self.config.tick_rate)

    def is_position_safe(self, x, y):
        """Check if a position is safe for spawning"""
        # Check the borders
        safe_distance = self.cell_size * SPAWN_SAFE_ZONE
        if (
            x < safe_distance
            or y < safe_distance
            or x > self.game_width - safe_distance
            or y > self.game_height - safe_distance
        ):
            return False

        # Check other trains and wagons
        for train in self.trains.values():
            # Distance to the train
            train_x, train_y = train.position
            if abs(train_x - x) < safe_distance and abs(train_y - y) < safe_distance:
                return False

            # Distance to wagons
            for wagon_x, wagon_y in train.wagons:
                if (
                    abs(wagon_x - x) < safe_distance
                    and abs(wagon_y - y) < safe_distance
                ):
                    return False

        # Check delivery zone
        delivery_zone = self.delivery_zone
        if (
            x > delivery_zone.x
            and x < delivery_zone.x + delivery_zone.width
            and y > delivery_zone.y
            and y < delivery_zone.y + delivery_zone.height
        ):
            return False

        # Check other passengers
        for passenger in self.passengers:
            if passenger != self and (x, y) == passenger.position:
                return False

        return True

    def get_safe_spawn_position(self, max_attempts=100):
        """Find a safe position for spawning"""
        for _ in range(max_attempts):
            # Position aligned on the grid
            x = (
                random.randint(
                    SPAWN_SAFE_ZONE,
                    (self.game_width // self.cell_size) - SPAWN_SAFE_ZONE,
                )
                * self.cell_size
            )
            y = (
                random.randint(
                    SPAWN_SAFE_ZONE,
                    (self.game_height // self.cell_size) - SPAWN_SAFE_ZONE,
                )
                * self.cell_size
            )

            if self.is_position_safe(x, y):
                return x, y

        # Default position at the center
        center_x = (self.game_width // 2) // self.cell_size * self.cell_size
        center_y = (self.game_height // 2) // self.cell_size * self.cell_size
        logger.warning(f"Using default center position: ({center_x}, {center_y})")
        return center_x, center_y

    def update_passengers_count(self):
        """Update the number of passengers based on the number of trains"""
        # Calculate the desired number of passengers based on the number of alive trains
        self.desired_passengers = (
            len([train for train in self.trains.values() if train.alive])
        ) // TRAINS_PASSENGER_RATIO

        # Add or remove passengers if necessary
        changed = False
        while len(self.passengers) < self.desired_passengers:
            new_passenger = Passenger(self)
            self.passengers.append(new_passenger)
            changed = True
            logger.debug("Added new passenger")

        if changed:
            self._dirty["passengers"] = True

    def initialize_game_size(self, num_clients):
        """Initialize game size based on number of connected clients"""
        if not self.game_started:
            # Calculate initial game size based on number of clients
            self.game_width = ORIGINAL_GAME_WIDTH + (num_clients * GAME_SIZE_INCREMENT)
            self.game_height = ORIGINAL_GAME_HEIGHT + (
                num_clients * GAME_SIZE_INCREMENT
            )

            self.new_game_width = self.game_width
            self.new_game_height = self.game_height
            self._dirty["size"] = True
            self._dirty["cell_size"] = True
            self.game_started = True
            logger.info(
                f"Game started with size {self.game_width}x{self.game_height} for {num_clients} clients"
            )

    def add_train(self, agent_name):
        """Add a new train to the game"""
        # Check the cooldown
        if agent_name in self.dead_trains:
            elapsed = time.time() - self.dead_trains[agent_name]
            if elapsed < self.config.respawn_cooldown_seconds:
                logger.debug(
                    f"Train {agent_name} still in cooldown for {self.config.respawn_cooldown_seconds - elapsed:.1f}s"
                )
                return False
            else:
                del self.dead_trains[agent_name]

        # Create the new train
        spawn_pos = self.get_safe_spawn_position()
        if spawn_pos:
            # If the agent name is in the train_colors dictionary, use the color, otherwise generate a random color
            if agent_name in self.train_colors:
                train_color = self.train_colors[agent_name]
            else:
                train_color = generate_random_non_blue_color()

            self.trains[agent_name] = Train(
                spawn_pos[0],
                spawn_pos[1],
                agent_name,
                train_color,
                self.handle_train_death,
                self.config.tick_rate,
            )
            self.update_passengers_count()
            return True
        return False

    def send_cooldown(self, agent_name):
        """Remove a train and update game size"""
        if agent_name in self.trains:
            # Register the death time
            self.dead_trains[agent_name] = time.time()

            # Clean up the last delivery time for this train
            if agent_name in self.last_delivery_times:
                del self.last_delivery_times[agent_name]

            # Notify the client of the cooldown
            self.send_cooldown_notification(
                agent_name, self.config.respawn_cooldown_seconds
            )

            # If the client is a bot
            if agent_name in self.ai_clients:
                # Get the client object
                client = self.ai_clients[agent_name]
                # Change the train's state
                client.agent.is_dead = True
                client.agent.death_time = time.time()
                client.agent.waiting_for_respawn = True
                client.agent.respawn_cooldown = self.config.respawn_cooldown_seconds
        else:
            logger.error(f"Train {agent_name} not found in game")
            return False

    def handle_train_death(self, agent_name):
        self.send_cooldown(agent_name)
        self.update_passengers_count()

    def get_train_cooldown(self, agent_name):
        """Get remaining cooldown time for a train"""
        if agent_name in self.dead_trains:
            elapsed = time.time() - self.dead_trains[agent_name]
            remaining = max(0, self.config.respawn_cooldown_seconds - elapsed)
            return remaining
        return 0

    def is_train_alive(self, agent_name):
        """Check if a train is alive"""
        return agent_name in self.trains and self.trains[agent_name].alive

    def check_collisions(self):
        for _, train in self.trains.items():
            train.update(
                self.trains,
                self.game_width,
                self.game_height,
                self.cell_size,
            )

            # Check for passenger collisions
            for passenger in self.passengers:
                if train.position == passenger.position:
                    # Increase train score

                    train.add_wagons(nb_wagons=passenger.value)

                    desired_passengers = (len(self.trains)) // TRAINS_PASSENGER_RATIO
                    if len(self.passengers) <= desired_passengers:
                        passenger.respawn()
                    else:
                        # Remove the passenger from the passengers list if there are too many
                        self.passengers.remove(passenger)
                        self._dirty["passengers"] = True

            # Check for delivery zone collisions
            if self.delivery_zone.contains(train.position):
                current_time = time.time()
                # Check if enough time has passed since the last delivery for this train
                if (
                    train.agent_name not in self.last_delivery_times
                    or current_time - self.last_delivery_times.get(train.agent_name, 0)
                    >= DELIVERY_COOLDOWN_TIME
                ):
                    # Slowly popping wagons and increasing score
                    wagon = train.pop_wagon()
                    if wagon:
                        train.update_score(train.score + 1)
                        # Update best score if needed
                        if train.score > self.best_scores.get(train.agent_name, 0):
                            self.best_scores[train.agent_name] = train.score
                        # Update the last delivery time for this train
                        self.last_delivery_times[train.agent_name] = current_time

    def update(self):
        """Update game state"""
        if not self.trains:  # Update only if there are trains
            return

        with self.lock:
            # Update all trains and check for death conditions
            # trains_to_remove = []
            self.check_collisions()
