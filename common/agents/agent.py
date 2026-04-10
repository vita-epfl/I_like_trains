import logging

from common.base_agent import BaseAgent
from common.messages import Move
from common.state import GameState

logger = logging.getLogger("agent")


class Agent(BaseAgent):
    def setup(self) -> None:
        """
        You can initialize any state you desire here. The state will
        persist across calls to get_move.

        E.g. this would be a good place to do self.random = random.Random(1234)
        if you want a reproducible source of randomness.
        """

    def get_move(self, game_state: GameState) -> Move:
        """
        Called regularly to get the next move for your bus. Implement
        an algorithm to control your bus here. You will be handing in this file.
        """
        return Move()
