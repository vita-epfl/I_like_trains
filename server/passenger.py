"""
Passenger class for the game "I Like Trains"
"""
import pygame
import random
import logging

# Configure logging
logger = logging.getLogger("server.passenger")

# Colors
RED = (255, 0, 0)

class Passenger:

    def __init__(self, game):
        self.game = game
        self.position = self.get_safe_spawn_position()

    def respawn(self):
        """Respawn the passenger at a random position"""
        new_pos = self.get_safe_spawn_position()
        if new_pos != self.position:
            self.position = new_pos
            self.game._dirty["passengers"] = True

    def get_safe_spawn_position(self):
        """Find a safe spawn position, far from trains and other passengers"""
        max_attempts = 100
        grid_size = self.game.grid_size

        for _ in range(max_attempts):
            # Position aligned on the grid
            x = (
                random.randint(0, (self.game.new_game_width // grid_size) - 1)
                * grid_size
            )
            y = (
                random.randint(0, (self.game.new_game_height // grid_size) - 1)
                * grid_size
            )

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

            if position_is_safe:
                # logger.debug(f"Passenger spawned at position {(x, y)}")
                return (x, y)

        # Default position if no safe position is found
        logger.warning("No safe position found for passenger spawn")
        return (0, 0)

    def get_safe_position(self):
        """Find a safe position away from trains and other passengers"""
        max_attempts = 100
        grid_size = self.game.grid_size

        for _ in range(max_attempts):
            # Position aligned on the grid
            x = (
                random.randint(0, (self.game.game_width // grid_size) - 1)
                * grid_size
            )
            y = (
                random.randint(0, (self.game.game_height // grid_size) - 1)
                * grid_size
            )

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

            if position_is_safe:
                # logger.debug(f"Passenger spawned at position {(x, y)}")
                return (x, y)

        # Default position if no safe position is found
        logger.warning("No safe position found for passenger spawn")
        return (0, 0)
"""
Passenger class for the game "I Like Trains"
"""
import pygame
import random
import logging

# Configure logging
logger = logging.getLogger("server.passenger")

# Colors
RED = (255, 0, 0)

class Passenger:

    def __init__(self, game):
        self.game = game
        self.position = self.get_safe_spawn_position()

    def respawn(self):
        """Respawn the passenger at a random position"""
        new_pos = self.get_safe_spawn_position()
        if new_pos != self.position:
            self.position = new_pos
            self.game._dirty["passengers"] = True

    def get_safe_spawn_position(self):
        """Find a safe spawn position, far from trains and other passengers"""
        max_attempts = 100
        grid_size = self.game.grid_size

        for _ in range(max_attempts):
            # Position aligned on the grid
            x = (
                random.randint(0, (self.game.new_game_width // grid_size) - 1)
                * grid_size
            )
            y = (
                random.randint(0, (self.game.new_game_height // grid_size) - 1)
                * grid_size
            )

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

            if position_is_safe:
                # logger.debug(f"Passenger spawned at position {(x, y)}")
                return (x, y)

        # Default position if no safe position is found
        logger.warning("No safe position found for passenger spawn")
        return (0, 0)

    def get_safe_position(self):
        """Find a safe position away from trains and other passengers"""
        max_attempts = 100
        grid_size = self.game.grid_size

        for _ in range(max_attempts):
            # Position aligned on the grid
            x = (
                random.randint(0, (self.game.game_width // grid_size) - 1)
                * grid_size
            )
            y = (
                random.randint(0, (self.game.game_height // grid_size) - 1)
                * grid_size
            )

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

            if position_is_safe:
                # logger.debug(f"Passenger spawned at position {(x, y)}")
                return (x, y)

        # Default position if no safe position is found
        logger.warning("No safe position found for passenger spawn")
        return (0, 0)
