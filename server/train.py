"""
Train class for the game "I Like Trains"
"""

import logging

from common.move import Move
from common.constants import REFERENCE_TICK_RATE

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("game_debug.log"), logging.StreamHandler()],
)

server_logger = logging.getLogger("server.train")

# INITIAL_SPEED controls when the train moves by default. The train moves every
# tick_rate / self.speed. A larger initial speed means the train will move more
# often. A smaller speed will mean it moves less often. Each time the train
# moves, it moves by cell_size.
INITIAL_SPEED = 10

SPEED_DECREMENT_COEFFICIENT = 0.95  # Speed reduction coefficient for each wagon

ACTIVATE_SPEED_BOOST = True  # Activate speed boost
BOOST_DURATION = 0.25  # Duration of speed boost in seconds
BOOST_COOLDOWN_DURATION = 10.0  # Cooldown duration for speed boost
BOOST_INTENSITY = 3  # Intensity of speed boost


class Train:
    def __init__(self, x, y, nickname, color, handle_train_death, tick_rate, reference_tick_rate):
        server_logger.debug(f"Creating train {nickname} at position {x}, {y}")
        self.position = (x, y)
        self.wagons = []
        self.new_direction = Move.RIGHT.value
        self.direction = Move.RIGHT.value
        self.previous_direction = Move.RIGHT.value
        self.nickname = nickname
        self.alive = True
        self.score = 0
        self.best_score = 0
        self.color = color
        self.handle_death = handle_train_death
        self.move_timer = 0
        self.speed = INITIAL_SPEED
        self.last_position = (x, y)

        self.tick_rate = tick_rate
        self.reference_tick_rate = reference_tick_rate
        # Dirty flags to track modifications
        self._dirty = {
            "position": True,
            "wagons": True,
            "direction": True,
            "score": True,
            "color": True,
            "alive": True,
            "boost_cooldown_active": True
        }
        # Speed boost properties
        self.speed_boost_active = False
        self.speed_boost_timer = 0
        self.boost_cooldown_active = False
        self.start_boost_cooldown_tick = 0
        self.boost_cooldown_ticks = 0
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

    def update(self, trains, screen_width, screen_height, cell_size, current_tick):
        """Update the train position"""
        self.current_tick = current_tick
        if not self.alive:
            return

        # Manage speed boost timer
        if self.speed_boost_active:
            self.speed_boost_timer -= (
                1 / self.reference_tick_rate
            )  # Decrement by seconds (assuming self.tick_rate ticks per second)
            if self.speed_boost_timer <= 0:
                # Reset speed boost
                self.speed_boost_active = False
                self.speed = self.normal_speed
                # self._dirty["speed"] = True

        # Manage boost cooldown timer
        if self.boost_cooldown_active:
            ticks_elapsed = self.current_tick - self.start_boost_cooldown_tick
            
            required_ticks = int((BOOST_COOLDOWN_DURATION + BOOST_DURATION) * self.reference_tick_rate)
            
            if ticks_elapsed >= required_ticks:
                server_logger.debug(f"Resetting cooldown for train {self.nickname}")
                # Reset cooldown
                self.boost_cooldown_active = False
                self._dirty["boost_cooldown_active"] = True
                
        # Increment movement timer - with fixed increment to ensure consistent speed across tickrates
        self.move_timer += 1

        # Simple threshold based on speed only - independent of tickrate
        move_threshold = REFERENCE_TICK_RATE / self.speed
        
        # Check if it's time to move
        if self.move_timer >= move_threshold:
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
            and len(self.wagons) > 0
        ):
            server_logger.debug(f"Applying speed boost to train {self.nickname}")
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

            # Start cooldown
            server_logger.debug(f"Starting cooldown for train {self.nickname}")
            self.boost_cooldown_active = True
            self.start_boost_cooldown_tick = self.current_tick
            self._dirty["boost_cooldown_active"] = True

            return last_wagon_pos
        else:
            return None

    def get_boost_cooldown_time(self):
        if self.boost_cooldown_active:
            ticks_elapsed = self.current_tick - self.start_boost_cooldown_tick
            return max(0, self.get_boost_cooldown_ticks() - ticks_elapsed)
        else:
            server_logger.warning(f"Train {self.nickname} not found in train_boost_cooldown_ticks")
            return 0

    def get_boost_cooldown_ticks(self):
        return int(BOOST_COOLDOWN_DURATION * self.reference_tick_rate)

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
            server_logger.warning(
                f"Invalid position for train {self.nickname} before move: {self.position}"
            )
            self.last_position = (0, 0)

        # Calculate new position
        new_x = self.position[0] + self.direction[0] * cell_size
        new_y = self.position[1] + self.direction[1] * cell_size
        new_position = (new_x, new_y)

        if not self.alive:
            return

        # Update wagons
        if self.wagons:
            self.wagons.insert(0, self.position)
            self.wagons.pop()
            self._dirty["wagons"] = True
            
        # Update position
        self.set_position(new_position)

        # Check collisions and bounds
        self.check_collisions_with_trains(new_position, trains)
        self.check_out_of_bounds(new_position, screen_width, screen_height)
        
    def to_dict(self):
        """Convert train to dictionary, returning only modified data"""
        data = {}
        if self._dirty["position"]:
            data["position"] = self.position
            self._dirty["position"] = False
            # Always include direction with position updates to ensure client stays in sync
            data["direction"] = self.direction
            self._dirty["direction"] = False
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
                    server_logger.warning(
                        f"Invalid wagon found in to_dict for train {self.nickname}: {wagon}, skipping"
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
        if self._dirty["boost_cooldown_active"]:
            data["boost_cooldown_active"] = self.boost_cooldown_active
            self._dirty["boost_cooldown_active"] = False
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

    def check_collisions_with_trains(self, new_position, all_trains):
        for wagon_pos in self.wagons:
            if new_position == wagon_pos:
                collision_msg = (
                    f"Train {self.nickname} collided with its own wagon at {wagon_pos}"
                )
                server_logger.info(collision_msg)
                death_reason = "self_collision"
                self.handle_death([self.nickname], death_reason)
                return True
            
        for train in all_trains.values():
            # If the train we are checking is dead or the train is ours, skip
            if train.nickname == self.nickname or not train.alive:
                continue

            if new_position == train.position:
                collision_msg = (
                    f"Train {self.nickname} collided with train {train.nickname}"
                )
                server_logger.info(collision_msg)
                death_reason = "collision_with_train"
                self.handle_death([self.nickname, train.nickname], death_reason)
                return True

            # Check collision with wagons
            for wagon_pos in train.wagons:
                if self.position == wagon_pos:
                    collision_msg = f"Train {self.nickname} collided with wagon of train {train.nickname}"
                    server_logger.info(collision_msg)
                    death_reason = "collision_with_wagon"
                    self.handle_death([self.nickname], death_reason)
                    return True

        return False

    def check_out_of_bounds(self, new_position, screen_width, screen_height):
        """Check if the train is out of the screen"""
        x, y = new_position
        if x < 0 or x >= screen_width or y < 0 or y >= screen_height:
            self.handle_death([self.nickname], "out_of_bounds")
            server_logger.debug(
                f"Train {self.nickname} is dead: out of the screen. Coordinates: {new_position}"
            )
            return True
        return False

    def reset(self):
        self.position = (-1, -1)  # Use an off-screen position instead of None
        self.wagons = []
        self.direction = Move.RIGHT.value
        self.new_direction = Move.RIGHT.value
        self.previous_direction = Move.RIGHT.value
        self._dirty = {
            "position": True,
            "wagons": True,
            "direction": True,
            "score": True,
            "color": True,
            "alive": True,
            "boost_cooldown_active": True
        }
