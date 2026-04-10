import asyncio
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

    def scipers(self) -> list[str]:
        return []

    def teamname(self) -> str:
        return "keyboard"

    def get_move(self, game_state: GameState) -> Move:
        # unreachable
        assert False

    async def async_get_move(self, game_state: GameState) -> Move:
        assert self.room_state is not None
        n = 0
        while True:
            n += 1
            if self.room_state.room_choice.slow and n > 10:
                self.key_event.waiting_for_input = True

            # Add a bit of latency here or the game is too fast
            await asyncio.sleep(1 / 60)

            move = self.key_to_move(game_state)
            if move is not None:
                self.key_event.waiting_for_input = False
                return move

    def key_to_move(self, game_state: GameState) -> Move | None:
        assert self.room_state is not None
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
            case "space":  # pick up
                # Simply try to pick up all the passengers, the server
                # will reject invalid ones.
                passenger_ids = {p.id for p in game_state.passengers.values()}
                return Move(pickup=passenger_ids)
            case "escape":  # drop off
                assert self.slot is not None
                passenger_ids = {p.id for p in game_state.buses[self.slot].passengers}
                return Move(drop=passenger_ids)
            case any:
                if any != "":
                    logger.debug(f"ignoring key: {self.key_event.key}")
                if self.room_state.room_choice.slow:
                    return None
                else:
                    return Move()
