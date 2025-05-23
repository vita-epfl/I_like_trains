from pydantic import BaseModel
from typing import Optional, List

from common.agent_config import AgentConfig


class GradingModeArgs(BaseModel):
    nb_players_per_session: List[int] = [1, 2, 3, 4]
    nb_runs_per_session: int = 50


class ServerConfig(BaseModel):
    # Host should either be 127.0.0.1 if you only want to accept local connections
    # or 0.0.0.0 if you want to accept local and remote connections.
    host: str = "0.0.0.0"

    # Port on which to listen.
    port: int = 5555

    # Numbers of trains in each room.
    # Can be an integer or the string "random".
    # If "random", a random number between 2 and 4 will be selected.
    nb_players_per_room: int | str = 2

    # Seed for random number generation. If None, a random seed will be generated.
    seed: Optional[int] = None

    # If True, allows multiple connections from the same IP address.
    allow_multiple_connections: bool = True

    # When a train hits another train or the game edge, it dies. This controls
    # how much time the user must wait before they can respawn a new train.
    respawn_cooldown_seconds: float = 5.0

    # How long to wait before considering a client as disconnected.
    client_timeout_seconds: float = 2.0

    # Controls the actual game speed (in frames per second).
    # This value determines how fast the game runs in real-time.
    # - Higher values make the game run faster than normal (e.g., 120 = 2x speed)
    # - Lower values make the game run slower than normal (e.g., 30 = 0.5x speed)
    # - Lower speeds can be useful for debugging purposes
    tick_rate: int = 60

    # Flag to enable the simulation mode for grading. 
    # In normal mode, we add all human players to the game first and then add bots if needed. 
    # In grading mode, we add all configured agents to the game.
    # If grading_mode is enabled, tick_rate is set to 10000 to run as fast as possible.
    grading_mode: bool = False

    # Grading mode specific arguments
    # The configuration from JSON: 
    # "grading_mode_args": {
    #         "nb_players_per_session": [1, 2, 3, 4],
    #         "nb_runs_per_session": 50
    #     }
    # is properly recognized by this model
    grading_mode_args: Optional[GradingModeArgs] = None

    # Duration of each game.
    game_duration_seconds: int = 300  # 300 seconds == 5 minutes

    # Amount of time clients will waiting for other clients to join before the
    # game is started with bots replacing any missing clients.
    waiting_time_before_bots_seconds: int = 30

    # Maximum number of passengers on a given square.
    max_passengers: int = 3

    # Controls how quickly passenger delivery happens. Depending on this value,
    # the size of the delivery zone, and the number of passengers, a train might
    # have to circle around to complete delivery of all their passengers.
    delivery_cooldown_seconds: float = 0.1

    # Path to an agent file. Change this path to point to one of your agents
    # to use when creating bots (when game_mode is "manual" or "agent" and a client
    # disconnects).
    ai_agent_file_name: str = "ai_agent.py"

    # Local agents configuration, add or remove agents you want to evaluate as needed
    agents: list[AgentConfig] = []
