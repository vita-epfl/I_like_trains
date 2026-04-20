import asyncio
from datetime import datetime
import logging

from common.base_agent import AgentWithKey
from common.messages import Dir, Move
from common.state import GameState

logger = logging.getLogger("agent")


class Agent(AgentWithKey):
    """
    An agent that you can control with your keyboard keys:
    - up/down/left/right arrows to move the agent
    - <space> to pickup passengers which are close by
    - <esc> to drop off all your passengers
    """

    def setup(self):
        super().setup()
        self.last_move = None

    async def async_get_move(self, game_state: GameState) -> Move:
        """
        The keyboard agent needs to use async_get_move() because
        we don't want to block the pygame keyboard handling task.
        """
        # Slow things down so that we don't crash into a wall as soon
        # as we press a key. The alternative would be to only move
        # one cell per key press, but that feels weird.
        t = datetime.now().timestamp()
        if self.last_move is not None:
            time_slice = 0.05 - (t - self.last_move)
            if time_slice > 0:
                await asyncio.sleep(time_slice)
        self.last_move = t

        n = 0
        while True:
            n += 1
            self.key_event.waiting_for_input = True
            await self.key_event.wait()
            move = self.key_to_move(game_state)
            if move is not None:
                self.key_event.waiting_for_input = False
                return move

    def get_move(self, game_state: GameState) -> Move:
        assert False  # unreachable since we are using async_get_move

    def key_to_move(self, game_state: GameState) -> Move | None:
        match self.key_event.key:
            case "up":
                self.key_event.waiting_for_input = False
                return Move(direction=Dir.UP)
            case "right":
                return Move(direction=Dir.RIGHT)
            case "down":
                return Move(direction=Dir.DOWN)
            case "left":
                return Move(direction=Dir.LEFT)
            case "space":
                # Simply try to pick up all the passengers, the server
                # will reject invalid ones.
                passenger_ids = {p.id for p in game_state.passengers.values()}
                return Move(pickup=passenger_ids)
            case "escape":
                # drop all our passengers, we'll score points if any match their
                # destination
                passenger_ids = {p.id for p in game_state.buses[self.slot].passengers}
                return Move(drop=passenger_ids)
            case any:
                self.key_event.clear()
                if any != "":
                    logger.debug(f"ignoring key: {self.key_event.key}")
                    return None
