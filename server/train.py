"""
Train class for the game "I Like Trains"
"""

import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("game_debug.log"), logging.StreamHandler()],
)

logger = logging.getLogger("server.train")

# Directions
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

# Train settings
# INITIAL_SPEED = 60  # Initial speed in pixels per second
INITIAL_SPEED = 10  # Initial speed in pixels per second: 5
SPEED_DECREMENT_COEFFICIENT = 0.95  # Speed reduction coefficient for each wagon

ACTIVATE_SPEED_BOOST = True  # Activate speed boost
BOOST_DURATION = 0.25  # Duration of speed boost in seconds
BOOST_COOLDOWN_DURATION = 10.0  # Cooldown duration for speed boost
BOOST_INTENSITY = 1.5  # Intensity of speed boost


class Train:
    def __init__(self, x, y, agent_name, color, handle_train_death, tick_rate):
        self.position = (x, y)
        self.wagons = []
        self.new_direction = (1, 0)
        self.direction = (1, 0)  # Starts right
        self.previous_direction = (1, 0)
        self.agent_name = agent_name
        self.alive = True
        self.score = 0
        self.best_score = 0
        self.color = color
        self.handle_death = handle_train_death
        self.move_timer = 0
        self.speed = INITIAL_SPEED
        self.last_position = (x, y)

        self.tick_rate = tick_rate
        # Dirty flags to track modifications
        self._dirty = {
            "position": True,
            "wagons": True,
            "direction": True,
            "score": True,
            "color": True,
            "alive": True,
            "speed": True,
            "speed_boost": True,
            "boost_cooldown": True,
        }
        self.client_logger = logging.getLogger("client.train")
        # Speed boost properties
        self.speed_boost_active = False
        self.speed_boost_timer = 0
        self.boost_cooldown_active = False
        self.boost_cooldown_timer = 0
        self.normal_speed = INITIAL_SPEED  # Store normal speed for after boost ends

    def get_position(self):
        """Return the train's position"""
        return self.position

    def is_opposite_direction(self, new_direction):
        """Check if the new direction is opposite to the previous direction"""
        return (
            new_direction[0] == -self.direction[0]
            and new_direction[1] == -self.direction[1]
        )

    def change_direction(self, new_direction):
        """Change the train's direction if possible"""
        if not self.is_opposite_direction(new_direction):
            self.new_direction = new_direction

    def update(self, trains, screen_width, screen_height, cell_size):
        """Update the train position"""
        if not self.alive:
            return

        # Manage speed boost timer
        if self.speed_boost_active:
            self.speed_boost_timer -= (
                1 / self.tick_rate
            )  # Decrement by seconds (assuming self.tick_rate ticks per second)
            if self.speed_boost_timer <= 0:
                # Reset speed boost
                self.speed_boost_active = False
                self.speed = self.normal_speed
                self._dirty["speed"] = True

                # Start cooldown
                self.boost_cooldown_active = True
                self.boost_cooldown_timer = BOOST_COOLDOWN_DURATION

        # Manage boost cooldown timer
        if self.boost_cooldown_active:
            self.boost_cooldown_timer -= 1 / self.tick_rate  # Decrement by seconds
            if self.boost_cooldown_timer <= 0:
                # Reset cooldown
                self.boost_cooldown_active = False

        # Increment movement timer
        self.move_timer += 1

        # Check if it's time to move
        if (
            self.move_timer >= self.tick_rate / self.speed
        ):  # self.tick_rate ticks per second
            self.move_timer = 0
            self.set_direction(self.new_direction)
            self.move(trains, screen_width, screen_height, cell_size)

    def add_wagons(self, nb_wagons=1):
        """Add wagons to the train"""
        for _ in range(nb_wagons):
            self.wagons.append(self.last_position)
        self._dirty["wagons"] = True
        self.update_speed()

    def pop_wagon(self):
        if self.wagons:
            # make it dirty
            self._dirty["wagons"] = True
            return self.wagons.pop()

        return None

    def clear_wagons(self):
        self.wagons.clear()
        self._dirty["wagons"] = True
        self.update_speed()

    def drop_wagon(self):
        """Drop the last wagon from the train and return its position"""
        if not self.alive:
            return None

        # Apply speed boost if enabled and not in cooldown
        if (
            ACTIVATE_SPEED_BOOST
            and not self.boost_cooldown_active
            and not self.speed_boost_active
            and len(self.wagons) > 1
        ):
            logger.debug(f"Applying speed boost to train {self.agent_name}")
            # Get the last wagon position
            last_wagon_pos = self.wagons[-1]

            # Drop one wagon
            self.wagons.pop()
            self._dirty["wagons"] = True
            # Store current normal speed before boost
            self.normal_speed = self.speed
            # Apply boost (e.g., double the current speed)
            self.speed *= BOOST_INTENSITY
            self.speed_boost_active = True
            self.speed_boost_timer = BOOST_DURATION  # 1 second boost
            self._dirty["speed"] = True

            return last_wagon_pos
        else:
            return None

    def update_speed(self):
        self.speed = INITIAL_SPEED * SPEED_DECREMENT_COEFFICIENT ** len(self.wagons)
        self._dirty["speed"] = True

    def move(self, trains, screen_width, screen_height, cell_size):
        """Regular interval movement"""
        if not self.alive:
            return

        # Save the last position before moving
        if isinstance(self.position, tuple) and len(self.position) == 2:
            self.last_position = self.position
        else:
            logger.warning(
                f"Invalid position for train {self.agent_name} before move: {self.position}"
            )
            self.last_position = (0, 0)

        # Calculate new position
        new_x = self.position[0] + self.direction[0] * cell_size
        new_y = self.position[1] + self.direction[1] * cell_size
        new_position = (new_x, new_y)

        # Check collisions and bounds
        self.check_collisions(new_position, trains)
        self.check_out_of_bounds(new_position, screen_width, screen_height)

        if not self.alive:
            return

        # Update wagons
        if self.wagons:
            self.wagons.insert(0, self.position)
            self.wagons.pop()
            self._dirty["wagons"] = True

        # Update position
        self.set_position(new_position)

    def kill(self):
        self.set_alive(False)
        self.handle_death(self.agent_name)
        self.reset()

    def serialize(self):
        """
        Convert train state to a serializable format for sending to the client
        """
        return {
            "position": self.position,
            "wagons": self.wagons,
            "direction": self.direction,
            "score": self.score,
            "color": self.color,
            "alive": self.alive,
            "speed": self.speed,
        }

    def to_dict(self):
        """Convert train to dictionary, returning only modified data"""
        data = {}
        if self._dirty["position"]:
            data["position"] = self.position
            self._dirty["position"] = False
        if self._dirty["wagons"]:
            # Verify that all wagons have valid positions
            valid_wagons = []
            for wagon in self.wagons:
                if (
                    wagon is not None
                    and isinstance(wagon, tuple)
                    and len(wagon) == 2
                    and isinstance(wagon[0], int)
                    and isinstance(wagon[1], int)
                ):
                    valid_wagons.append(wagon)
                else:
                    logger.warning(
                        f"Invalid wagon found in to_dict for train {self.agent_name}: {wagon}, skipping"
                    )
            data["wagons"] = valid_wagons
            self._dirty["wagons"] = False
        if self._dirty["direction"]:
            data["direction"] = self.direction
            self._dirty["direction"] = False
        if self._dirty["score"]:
            data["score"] = self.score
            self._dirty["score"] = False
        if self._dirty["color"]:
            data["color"] = self.color
            self._dirty["color"] = False
        if self._dirty["alive"]:
            data["alive"] = self.alive
            self._dirty["alive"] = False
        if self._dirty["speed"]:
            data["speed"] = self.speed
            self._dirty["speed"] = False

        return data

    def set_position(self, new_position):
        """Update train position"""
        if self.position != new_position:
            self.position = new_position
            self._dirty["position"] = True

    def set_direction(self, direction):
        """Change train direction"""
        if self.direction != direction:
            self.previous_direction = self.direction
            self.direction = direction
            self._dirty["direction"] = True

    def update_score(self, new_score):
        """Update train score"""
        if self.score != new_score:
            self.score = new_score
            self._dirty["score"] = True

        self.update_speed()

    def set_alive(self, alive):
        """Update train alive status"""
        if self.alive != alive:
            self.alive = alive
            self._dirty["alive"] = True

    def check_collisions(self, new_position, all_trains):
        for wagon_pos in self.wagons:
            if new_position == wagon_pos:
                collision_msg = f"Train {self.agent_name} collided with its own wagon at {wagon_pos}"
                logger.info(collision_msg)
                self.client_logger.info(collision_msg)
                self.kill()
                return True

        for train in all_trains.values():
            # If the train we are checking is dead or the train is ours, skip
            if train.agent_name == self.agent_name or not train.alive:
                continue

            if new_position == train.position:
                collision_msg = (
                    f"Train {self.agent_name} collided with train {train.agent_name}"
                )
                logger.info(collision_msg)
                self.client_logger.info(collision_msg)
                train.kill()
                self.kill()
                return True

            # Check collision with wagons
            for wagon_pos in train.wagons:
                if self.position == wagon_pos:
                    collision_msg = f"Train {self.agent_name} collided with wagon of train {train.agent_name}"
                    logger.info(collision_msg)
                    self.client_logger.info(collision_msg)
                    self.kill()
                    return True

        return False

    def check_out_of_bounds(self, new_position, screen_width, screen_height):
        """Check if the train is out of the screen"""
        x, y = new_position
        if x < 0 or x >= screen_width or y < 0 or y >= screen_height:
            self.kill()
            logger.debug(
                f"Train {self.agent_name} is dead: out of the screen. Coordinates: {new_position}"
            )
            return True
        return False

    def reset(self):
        self.position = (-1, -1)  # Use an off-screen position instead of None
        self.wagons = []
        self.direction = (1, 0)
        self.new_direction = (1, 0)
        self.previous_direction = (1, 0)
        self._dirty = {
            "position": True,
            "wagons": True,
            "direction": True,
            "score": True,
            "color": True,
            "alive": True,
            "speed": True,
            "speed_boost": True,
            "boost_cooldown": True,
        }
