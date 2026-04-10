from asyncio import IncompleteReadError, StreamReader, StreamWriter
from enum import Enum
import logging
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ValidationError

from common.state import GameState, PassengerId, RoomChoice, RoomState

# Used to ensure that the client and server are running the same version of the code.
NETWORK_MESSAGE_VERSION = 202601


def check_version(version: int) -> int:
    if version != NETWORK_MESSAGE_VERSION:
        raise ValueError(f"invalid version: {version} != {NETWORK_MESSAGE_VERSION}")
    return version


class Message(BaseModel):
    version: Annotated[int, AfterValidator(check_version)] = NETWORK_MESSAGE_VERSION

    # Messages sent from client => server
    join: JoinRequest | None = None
    move: MoveRequest | None = None

    # Messages sent from server => client
    room_update: RoomUpdate | None = None
    game_update: GameUpdate | None = None

    async def send(self, w: StreamWriter) -> None:
        """
        Send message. Catch and ignore all exceptions.
        """
        logger = logging.getLogger("network")
        try:
            data = bytes(self.model_dump_json(), encoding="utf-8")
            w.write(len(data).to_bytes(length=4, byteorder="big"))
            w.write(data)
            await w.drain()
        except (ConnectionResetError, BrokenPipeError) as e:
            logger.debug(e)
        except Exception as e:
            logger.info(e)

    @staticmethod
    async def recv(r: StreamReader) -> Message | None:
        """
        Receives a Message from the network. If an exception
        happens, we treat it as a disconnected client.
        """
        logger = logging.getLogger("network")

        try:
            expected_len = int.from_bytes(await r.readexactly(4), byteorder="big")
            data = await r.readexactly(expected_len)
            msg = Message.model_validate_json(data)
            return msg
        except IncompleteReadError as e:
            if len(e.partial) != 0:
                logger.debug(e)
            return None
        except ValidationError as e:
            logger.debug(e)
            return None
        except Exception as e:
            logger.info(e)
            return None


class JoinRequest(BaseModel):
    teamname: str
    room_choice: RoomChoice


class RoomUpdate(BaseModel):
    # your slot in the room. This uniquely identifies you, e.g. if you connect with two
    # of your agents at the same time or if two teams have the same name.
    slot: int
    room_state: RoomState


class GameUpdate(BaseModel):
    game_state: GameState
    move_expected: bool


class MoveRequest(BaseModel):
    move: Move
    # The client sends back the tick so that the server can ignore
    # the move if it arrives late.
    tick: int


class Move(BaseModel):
    direction: Dir | None = (
        None  # Which way you want to move. None means stay in place.
    )
    pickup: set[PassengerId] = set()  # Passengers to pick up.
    drop: set[PassengerId] = set()  # Passengers to drop off.


class Dir(Enum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3
