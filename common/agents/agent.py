import logging

from common.base_agent import BaseAgent
from common.messages import Dir, Move
from common.state import GameState

logger = logging.getLogger("agent")


class Agent(BaseAgent):
    def scipers(self) -> list[str]:
        return ["112233", "445566"]

    def teamname(self) -> str:
        return "put-a-cool-name-here"

    def setup(self) -> None:
        """
        You can initialize any state you desire here. The state will
        persist across calls to get_move.

        E.g. this would be a good place to do self.random = random.Random(1234)
        if you want a reproducible source of randomness.
        """

    def get_move(self, game_state: GameState) -> Move:
        """
        Called regularly called to get the next move for your bus. Implement
        an algorithm to control your bus here. You will be handing in this file.

        You can assert self.slot and self.room_state are set.
        """
        assert self.slot is not None
        assert self.room_state is not None
        logger.debug(f"slot: {self.slot}, tick: {game_state.tick}")
        return Move(direction=Dir.UP)
