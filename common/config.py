import logging
import sys

from pydantic import BaseModel, Field, ValidationError

from common.state import RoomChoice


class ClientConfig(BaseModel):
    # Host we want to connect to. Use 127.0.0.1 if you want to connect to your local machine.
    connect_to: str = "127.0.0.1"

    # Port server is listening on.
    port: int = 5555

    teamname: str = "incognito"

    # Where your code is located.
    agent_filename: str = "agent.py"

    # If agent_timeout_seconds is set, the client code will
    # respond with an empty move if agent_timeout_seconds has
    # elapsed. This reflects how grading works.
    #
    # If agent_timeout_seconds is 0, the client code will
    # wait forever for the agent to respond, which can
    # make debugging easier.
    agent_timeout_seconds: float = 0.150

    # Configures the room you want to play in
    room_choice: RoomChoice = RoomChoice()

    # How many players in total the room should have
    total_players: int = Field(default=2, ge=1, le=16)

    # Minimum number of staff agents you want to play against
    min_staff_agents: int = Field(default=0, ge=0, le=15)

    # UI stuff
    window_width: int = 800
    window_height: int = 600
    ui_size: int = 1
    font_size: int = 14


class ServerConfig(BaseModel):
    # Set to true if you only want to accept clients on your local machine.
    # Set to false to allow clients from local and remote machines. You might
    # have to configure one or more network firewall rules for remote connections
    # to work.
    localhost_only: bool = True

    # Port on which to listen.
    port: int = 5555

    # Seed for random number generation.
    # If the seed is set, the server will always pick the same
    # map, same starting positions for the buses, and
    # same starting positions for the passengers. Useful for
    # debugging.
    seed: int | None = None

    # Duration of game in ticks per player.
    game_duration_ticks: int = 7200

    desired_passengers: int = 10
    respawn_ticks: int = 300
    bus_min_length: int = 2
    bus_max_length: int = 5
    max_passengers: int = 4  # how many passengers you can have on one bus
    maps: dict[str, str] = {}  # dictionnary of map name to path

    # Agents used to fill rooms
    agents: dict[str, str] = {}  # dictionnary of agent name to path

    # How long to wait before a room gets filled with staff agents and starts
    room_max_wait_game_start_seconds: float = 30.0

    # How long to allow local agents to run.
    # The code returns an empty move if the timeout gets triggered.
    local_agent_timeout_seconds: float = 0.150

    # How long to wait for a client to respond.
    # At grading time, we plan to set this value to 0.2 seconds (i.e. 200 ms)
    # The default value is slightly higher ot take network lag into account.
    max_client_latency_seconds: float = 3.0

    # When spawning passengers, we look for cells which are this distance
    # away from existing buses
    spawn_passenger_away_from_bus_distance: int = 3

    # When a bus crashes or passengers aren't dropped at their destination,
    # we try to place the passenger this distance within the front of the bus
    drop_passenger_from_bus_distance: int = 3

    # Possible values for passengers
    passenger_values: set[int] = {10, 15, 20, 25, 30}

    # How close the front of the bus needs to be to pick up a passenger
    passenger_pickup_from_bus_distance: int = 1

    # If set, stores results to a sqlite database
    results_database: None | str = None


class GradingConfig(BaseModel):
    # How many iterations to perform for each combination of
    # number of players * map * agent being graded
    iterations: int = 10

    # Seed used to ensure each agent is graded the same way. The grading seed
    # is used to deterministically generate per-run seeds.
    seed: int = 1000

    # Agents to grade. Files are loaded from grading/agents.
    agents_to_grade: dict[str, str] = {}

    # Staff agents which can be used to fill rooms. Files are loaded from
    # common/agents (same as ServerConfig.agents).
    staff_agents: dict[str, str] = {}
    min_staff_agents: int = 0
    max_staff_agents: int = 3

    # Path to the csv file where results are appended.
    output_file: str = "grading_results.csv"

    # How long to allow an agent to respond. An empty move is used when the
    # timeout fires.
    agent_timeout_seconds: float = 0.150

    # The following fields mirror the corresponding ServerConfig fields and
    # are used when building the room and the game.
    game_duration_ticks: int = 7200
    desired_passengers: int = 10
    respawn_ticks: int = 300
    bus_min_length: int = 2
    bus_max_length: int = 5
    max_passengers: int = 4
    maps: dict[str, str] = {}
    spawn_passenger_away_from_bus_distance: int = 3
    drop_passenger_from_bus_distance: int = 3
    passenger_values: set[int] = {10, 15, 20, 25, 30}
    passenger_pickup_from_bus_distance: int = 1


class Config(BaseModel):
    """
    Load config.json (or whatever filename was passed on the command line)

    The json config file is mapped to this object. As a result:
    - it is clear which fields can appear in the config file
    - the purpose of each field is properly documented
    - there's an efficient way to handle default values
    - there's a single Config object that gets passed around the codebase
    """

    client: ClientConfig = ClientConfig()
    server: ServerConfig = ServerConfig()
    grading: GradingConfig = GradingConfig()
    loggers: dict[str, str] = {}  # logger to log level mapping

    @staticmethod
    def load(filename: str) -> Config:
        """
        Loads a JSON config file and returns an instance of Config.
        """

        try:
            with open(filename, "r") as f:
                config = Config.model_validate_json("".join(f))
                for logger, level in config.loggers.items():
                    log = logging.getLogger(logger)
                    log.setLevel(level)
                return config
        except ValidationError as e:
            print(f"Failed to parse {filename}, check your changes.", file=sys.stderr)
            raise e
        except FileNotFoundError as e:
            print(
                f"\nError: Configuration file '{filename}' not found.\n\n"
                f"Please copy the template file to create your config:\n"
                f"  - On Linux/MacOS/Unix: cp config.json.template config.json\n"
                f"  - On Windows (Command Prompt): copy config.json.template config.json\n"
                f"  - On Windows (PowerShell): Copy-Item -Path config.json.template -Destination config.json\n\n"
                f"See the README.md for more details.\n",
                file=sys.stderr,
            )
            raise e
