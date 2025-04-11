import random
import logging


# Use the logger configured in server.py
logger = logging.getLogger("server.delivery_zone")


class DeliveryZone:
    """
    Represents the area where passengers must be dropped off in order to earn points.

    DeliveryZones are placed randomly. Their size depends on the number of players.
    """

    def __init__(self, game_width, game_height, cell_size, nb_players):
        initial_width = 2
        initial_height = 2

        random_increased_dimension = random.choice(["width", "height"])
        self.width = (
            cell_size * (initial_width + nb_players)
            if random_increased_dimension == "width"
            else cell_size * initial_width
        )
        self.height = (
            cell_size * (initial_height + nb_players)
            if random_increased_dimension == "height"
            else cell_size * initial_height
        )

        self.x = cell_size * random.randint(
            0, (game_width // cell_size - 1 - self.width // cell_size)
        )
        self.y = cell_size * random.randint(
            0, (game_height // cell_size - 1 - self.height // cell_size)
        )

    def contains(self, position):
        x, y = position
        return (
            x >= self.x
            and x < self.x + self.width
            and y >= self.y
            and y < self.y + self.height
        )

    def to_dict(self):
        return {
            "height": self.height,
            "width": self.width,
            "position": (self.x, self.y),
        }
