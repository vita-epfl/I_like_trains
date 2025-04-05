import random
import logging

# Configure logging
logger = logging.getLogger("server.passenger")


class Passenger:
    # TODO(Alok): Passenger should not depend on game -- we have a circular dependency indicative of a structural issue.
    def __init__(self, game):
        self.game = game
        self.position = self.get_safe_spawn_position()
        self.value = random.randint(1, self.game.config.max_passengers)

    def respawn(self):
        """
        Respawn the passenger at a random position.
        """
        new_pos = self.get_safe_spawn_position()
        self.position = new_pos
        self.value = random.randint(1, self.game.config.max_passengers)
        self.game._dirty["passengers"] = True

    def get_safe_spawn_position(self):
        """
        Find a safe spawn position, far from trains and other passengers.
        If no safe position can be found after a large number of attempts, we'll
        return a random position (potentially on top of an existing train, passenger, or delivery zone).
        """
        max_attempts = 200
        cell_size = self.game.cell_size

        for _ in range(max_attempts):
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

            pos = (x, y)
            if self.is_safe_position(pos):
                return pos

        # Return a random position if no safe position is found
        logger.warning("No safe position found for passenger spawn")
        return pos

    def is_safe_position(self, pos):
        # Check collision with trains and their wagons
        for train in self.game.trains.values():
            if pos == train.position:
                return False

            for wagon_pos in train.wagons:
                if pos == wagon_pos:
                    return False

        # Check collision with other passengers
        for passenger in self.game.passengers:
            if passenger != self and pos == passenger.position:
                return False

        # Check collision with delivery zone
        delivery_zone = self.game.delivery_zone
        if delivery_zone.contains(pos):
            return False

        return True

    def to_dict(self):
        return {"position": self.position, "value": self.value}
