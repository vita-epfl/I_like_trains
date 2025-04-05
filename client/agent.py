import random
from client.base_agent import BaseAgent

# Student scipers, will be automatically used to evaluate your code
SCIPERS = ["000001", "000002", "000003"]

BASE_DIRECTIONS = [
    (0, -1),  # Up
    (1, 0),  # Right
    (0, 1),  # Down
    (-1, 0),  # Left
]


class Agent(BaseAgent):
    def get_direction(self):
        """
        This method is regularly called by the client to get the next direction of the train.
        """
        return random.choice(BASE_DIRECTIONS)  # Replace this with your own logic
