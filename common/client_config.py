from enum import Enum
from pydantic import BaseModel

from common.agent_config import AgentConfig


class ManualConfig(BaseModel):
    nickname: str


class GameMode(Enum):
    MANUAL = "manual"
    AGENT = "agent"
    OBSERVER = "observer"


class ClientConfig(BaseModel):
    # Host we want to connect to. Use 127.0.0.1 if you want to connect to a local server.
    host: str = "127.0.0.1"

    # Port server is listening on.
    port: int = 5555

    # Size of leaderboard in pixels
    leaderboard_width: int = 280

    # When your train hits another train or the edge of the game, it dies.
    # It then automatically respawns after a period of time, unless manual_spawn
    # is set to True, in which case you have to hit "SPACE" to respawn.
    manual_spawn: bool = False

    # When game_mode is set to MANUAL, you control the train using the arrow keys + 'd'
    # to drop wagons. When game_mode is set to AGENT, the agent code is called.
    # When game_mode is set to OBSERVER, the agents are.
    game_mode: GameMode = GameMode.MANUAL

    # How long to wait before considering a server as disconnected.
    server_timeout_seconds: float = 2.0

    # Sciper
    sciper: str = "000000"

    # Competitive agent configuration, change the sciper to yours, and the nickname to
    # your "nickname". Modify the agent_file_name to the agent file name you want to use
    # from the "agents" folder.
    agent: AgentConfig

    # Manual agent configuration
    manual: ManualConfig

    # If True, the client will generate a random suffix for the nickname, allows you
    # to have multiple clients with the same nickname in the config
    add_suffix_to_nickname: bool = False

    # Performance profiling settings
    enable_profiling: bool = False
    profiling_output_dir: str = "profiling_results"
    profiling_interval_seconds: float = 1.0
