"""
Passenger class for the game "I Like Trains"
"""

import random
import logging


# Configure logging
logger = logging.getLogger("server.passenger")

# Colors
RED = (255, 0, 0)

MAX_POINTS_VALUE = 3


class Passenger:
    def __init__(self, game):
        self.game = game
        self.position = self.get_safe_spawn_position()
        self.value = random.randint(1, MAX_POINTS_VALUE)

    def respawn(self):
        """Respawn the passenger at a random position"""
        new_pos = self.get_safe_spawn_position()
        if new_pos != self.position:
            self.position = new_pos
            self.value = random.randint(1, MAX_POINTS_VALUE)
            self.game._dirty["passengers"] = True

    def get_safe_spawn_position(self):
        """Find a safe spawn position, far from trains and other passengers"""
        max_attempts = 200
        cell_size = self.game.cell_size

        for _ in range(max_attempts):
            # Position aligned on the grid
            x = (
                random.randint(0, (self.game.new_game_width // cell_size) - 1)
                * cell_size
            )
            y = (
                random.randint(0, (self.game.new_game_height // cell_size) - 1)
                * cell_size
            )

            if (
                x < 0
                or x >= self.game.new_game_width
                or y < 0
                or y >= self.game.new_game_height
            ):
                logger.error(
                    f"Invalid spawn position: {(x, y)}, game dimensions: {self.game.new_game_width}x{self.game.new_game_height}"
                )
                continue

            position_is_safe = True

            # Check collision with trains and their wagons
            for train in self.game.trains.values():
                if (x, y) == train.position:
                    position_is_safe = False
                    break

                for wagon_pos in train.wagons:
                    if (x, y) == wagon_pos:
                        position_is_safe = False
                        break

                if not position_is_safe:
                    break

            # Check collision with other passengers
            for passenger in self.game.passengers:
                if passenger != self and (x, y) == passenger.position:
                    position_is_safe = False
                    break

            # Check collision with delivery zone
            delivery_zone = self.game.delivery_zone
            if delivery_zone.is_position_in_delivery_zone(x, y):
                position_is_safe = False
                break

            if position_is_safe:
                return (x, y)

        # Default position if no safe position is found
        logger.warning("No safe position found for passenger spawn")
        # Return random position
        return (
            random.randint(0, self.game.new_game_width // cell_size - 1) * cell_size,
            random.randint(0, self.game.new_game_height // cell_size - 1) * cell_size,
        )

    def to_dict(self):
        return {"position": self.position, "value": self.value}
