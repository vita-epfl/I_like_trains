from enum import Enum
from pydantic import BaseModel


class ControlMode(Enum):
    MANUAL = "manual"
    AGENT = "agent"


class ClientConfig(BaseModel):
    # SCIPER used to identify the agent. Must be unique (the server only allows
    # one connection from a given SCIPER at a time).
    sciper: str = "123456"

    # Name used to identify the agent. Must be unique (the server only allows
    # one train_name at a time).
    train_name: str = "r1x9"

    # Host we want to connect to. Use 127.0.0.1 if you want to connect to a local server.
    host: str = "127.0.0.1"

    # Port server is listening on.
    port: int = 5555

    # Size of game window in pixels
    screen_width: int = 500
    screen_height: int = 360

    # Size of cells in pixels
    # TODO(alok): shouldn't this be infered from screen_width and screen_height?
    cell_size: int = 20

    # Size of leaderboard in pixels
    # TODO(alok): shouldn't this simply be screen_width - screen_height?
    leaderboard_width: int = 280

    # When your train hits another train or the edge of the game, it dies.
    # It then automatically respawns after a period of time, unless manual_spawn
    # is set to True, in which case you have to hit "SPACE" to respawn.
    manual_spawn: bool = False

    # When control_mode is set to MANUAL, you control the train using the arrow keys + 'd'
    # to drop wagons.
    # When control_mode is set to AGENT, the agent code is called.
    control_mode: ControlMode = ControlMode.MANUAL

    # How long to wait before considering a server as disconnected.
    server_timeout_seconds: float = 2.0
