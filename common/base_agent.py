import asyncio
from abc import ABC, abstractmethod

from common.messages import Move
from common.state import GameState, RoomState, Slot


class BaseAgent(ABC):
    """
    Abstract base class for agents.
    """

    def __init__(self, room_state: RoomState, slot: Slot):
        self.room_state = room_state
        self.slot = slot
        # override self.sleep in child classes if you want to
        # slow down your agent for debugging purpose
        self.sleep: float = 0
        self.setup()

    def setup(self) -> None:
        """
        Override this method if you want to perform any one-time setup.
        """

    async def async_get_move(self, game_state: GameState) -> Move:
        if self.sleep > 0:
            await asyncio.sleep(self.sleep)
        return self.get_move(game_state)

    @abstractmethod
    def get_move(self, game_state: GameState) -> Move:
        """
        Returns the move the agent has decided to make.
        """


class AgentWithKey(BaseAgent):
    """
    Used by keyboard.py
    """

    def setup(self):
        self.key_event = KeyEvent()


class KeyEvent(asyncio.Event):
    def __init__(self):
        super().__init__()
        self.key: str = ""
        self.waiting_for_input = False
