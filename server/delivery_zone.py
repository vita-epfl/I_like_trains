import random
import logging


# Use the logger configured in server.py
logger = logging.getLogger("server.delivery_zone")


class DeliveryZone:
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
        logger.debug(
            f"Delivery zone initialized: {self.get_state()}, game size: {game_width}x{game_height}"
        )

    def is_position_in_delivery_zone(self, x, y):
        return (
            x >= self.x
            and x < self.x + self.width
            and y >= self.y
            and y < self.y + self.height
        )

    def get_state(self):
        return {
            "height": self.height,
            "width": self.width,
            "position": (self.x, self.y),
        }
