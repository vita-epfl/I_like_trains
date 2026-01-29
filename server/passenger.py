import logging

# Configure logging
logger = logging.getLogger("server.passenger")


class Passenger:
    # TODO(Alok): Passenger should not depend on game -- we have a circular dependency indicative of a structural issue.
    def __init__(self, game):
        self.game = game
        self.position = self.get_safe_spawn_position()
        self.value = self.game.random.randint(1, self.game.config.max_passengers)
        self._dirty = True  # Track if passenger data has changed
        self._id = id(self)  # Unique identifier for delta updates

    def respawn(self):
        """
        Respawn the passenger at a random position.
        """
        new_pos = self.get_safe_spawn_position()
        self.position = new_pos
        self.value = self.game.random.randint(1, self.game.config.max_passengers)
        self._dirty = True
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
                self.game.random.randint(0, (self.game.game_width // cell_size) - 1)
                * cell_size
            )
            y = (
                self.game.random.randint(0, (self.game.game_height // cell_size) - 1)
                * cell_size
            )

            if (
                x < 0
                or x >= self.game.game_width
                or y < 0
                or y >= self.game.game_height
            ):
                logger.error(
                    f"Invalid spawn position: {(x, y)}, game dimensions: {self.game.game_width}x{self.game.game_height}"
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

    def to_dict(self, include_id: bool = False):
        """Convert passenger to dictionary. Optionally include ID for delta updates."""
        data = {"position": self.position, "value": self.value}
        if include_id:
            data["id"] = self._id
        return data
    
    def to_dict_if_dirty(self, include_id: bool = True):
        """Return dict only if passenger has changed, then clear dirty flag."""
        if self._dirty:
            self._dirty = False
            data = {"position": self.position, "value": self.value}
            if include_id:
                data["id"] = self._id
            return data
        return None
    
    def mark_dirty(self):
        """Mark passenger as needing to be sent to clients."""
        self._dirty = True
        self.game._dirty["passengers"] = True
