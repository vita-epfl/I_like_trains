from __future__ import annotations

import random
import logging
import math
from typing import Any


# Use the logger configured in server.py
logger = logging.getLogger("server.delivery_zone")


class DeliveryZone:
    """
    Represents the area where passengers must be dropped off in order to earn points.

    DeliveryZones are placed randomly. Their size depends on the number of players.

    Coordinate System:
        - The game uses a pixel-based coordinate system where (0, 0) is the TOP-LEFT corner.
        - X increases to the RIGHT.
        - Y increases DOWNWARD.

    Attributes:
        x (int): The X coordinate of the TOP-LEFT corner of the delivery zone (in pixels).
        y (int): The Y coordinate of the TOP-LEFT corner of the delivery zone (in pixels).
        width (int): The width of the delivery zone (in pixels), extending to the RIGHT from x.
        height (int): The height of the delivery zone (in pixels), extending DOWNWARD from y.

    The delivery zone occupies the rectangular area:
        - From (x, y) at the top-left corner
        - To (x + width, y + height) at the bottom-right corner (exclusive)

    Example:
        If x=100, y=50, width=60, height=40:
        - Top-left corner: (100, 50)
        - Top-right corner: (159, 50)
        - Bottom-left corner: (100, 89)
        - Bottom-right corner: (159, 89)
        - A position (px, py) is inside if: x <= px < x+width AND y <= py < y+height

    The `to_dict()` method returns:
        {
            "position": (x, y),  # Top-left corner coordinates
            "width": width,       # Width in pixels
            "height": height      # Height in pixels
        }
    """

    def __init__(self, game_width: int, game_height: int, cell_size: int, nb_players: int, random_gen: random.Random | None = None) -> None:
        self.random: random.Random = random_gen if random_gen is not None else random

        # Calculate a factor based on square root for slower growth
        # Ensure nb_players is positive. Use sqrt + small linear term.
        player_factor = (math.isqrt(nb_players) ) if nb_players > 0 else 0

        # Both dimensions should depend on player factor
        width_with_factor = player_factor
        height_with_factor = player_factor

        # Randomly choose which dimension gets an extra boost
        random_increased_dimension = self.random.choice(["width", "height"])
        
        # Apply cell size scaling to final dimensions
        self.width = cell_size * (
            width_with_factor + player_factor if random_increased_dimension == "width" else width_with_factor
        )
        self.height = cell_size * (
            height_with_factor + player_factor if random_increased_dimension == "height" else height_with_factor
        )
        
        # Calculate and clamp the upper bound for x
        max_x_offset = game_width // cell_size - 1 - self.width // cell_size
        upper_bound_x = max(0, max_x_offset)
        self.x = cell_size * self.random.randint(0, upper_bound_x)
        
        # Calculate and clamp the upper bound for y
        max_y_offset = (
            (game_height // cell_size - 1 - self.height // cell_size)
        )
        # Ensure the upper bound is not negative
        upper_bound_y = max(0, max_y_offset)

        self.y: int = cell_size * self.random.randint(0, upper_bound_y)

        logger.debug(f"Delivery zone: top-left=({self.x}, {self.y}), bottom-right=({self.x + self.width}, {self.y + self.height}), size={self.width}x{self.height}")


    def contains(self, position: tuple[int, int]) -> bool:
        """
        Check if a position is inside the delivery zone.

        Args:
            position: A tuple (x, y) representing the position to check (in pixels).

        Returns:
            True if the position is inside the delivery zone, False otherwise.

        Note:
            The check uses inclusive lower bounds and exclusive upper bounds:
            x <= position_x < x + width AND y <= position_y < y + height
        """
        x, y = position
        return (
            x >= self.x
            and x < self.x + self.width
            and y >= self.y
            and y < self.y + self.height
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the delivery zone to a dictionary for network transmission.

        Returns:
            A dictionary with:
                - "position": (x, y) tuple representing the TOP-LEFT corner (in pixels)
                - "width": width of the zone in pixels (extends to the right)
                - "height": height of the zone in pixels (extends downward)
        """
        return {
            "height": self.height,
            "width": self.width,
            "position": (self.x, self.y),
        }
