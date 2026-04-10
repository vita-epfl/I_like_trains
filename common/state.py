from pydantic import BaseModel, Field
from typing import Annotated
from pydantic import BeforeValidator, PlainSerializer

# State which is shared between the server and client.
# At a highlevel, there's a RoomState that gets created when
# the first client wants to join a room. There's a GameState which
# changes every tick and gets sent to the clients.

type PassengerId = int
type Dest = str
type Slot = int


class RoomState(BaseModel):
    players: set[Player]
    room_choice: RoomChoice
    created_at: int  # unix timestamp
    room_max_wait_game_start_seconds: float
    game_duration_ticks: int

    # how many passengers are going to be available for picking up
    desired_passengers: int

    respawn_ticks: int  # how long you have to wait after crashing
    bus_length: int  # how many segments each bus has
    max_passengers: int  # max number of passengers a bus can carry

    # When spawning passengers, we look for cells which are this distance
    # away from existing buses
    spawn_passenger_away_from_bus_distance: int

    # When a bus crashes or passengers aren't dropped at their destination,
    # we try to place the passenger this distance within the front of the bus
    drop_passenger_from_bus_distance: int

    # Possible values for passengers
    passenger_values: set[int]

    # How close the front of the bus needs to be to pick up a passenger
    passenger_pickup_from_bus_distance: int

    map: Map


class RoomChoice(BaseModel, frozen=True):
    # How many players in total the room should have.
    # Must be a value between 1 and 16
    total_players: int = Field(default=2, ge=1, le=16)

    # minimum number of staff agents you want to play with
    # Must be a value between 1 and total_players-1
    min_staff_agents: int = 1

    # pick a map or set to None to play on a random one
    map_choice: str | None = None


class Map(BaseModel):
    name: str
    width: int
    height: int
    # places where buses can go
    available_cells: set[Pos]
    # places where you must drop off passengers to score points
    delivery_zones: dict[Pos, Dest]


class GameState(BaseModel):
    tick: int = 0
    buses: dict[Slot, Bus] = {}  # dictionary containing all the buses in play
    # passengers waiting to be picked up
    passengers: dict[Pos, Passenger] = {}
    scores: dict[Slot, int] = {}


class Bus(BaseModel):
    # positions representing the bus segments:
    # - positions[0] is the front
    # - positions[-1] is the back
    positions: list[Pos] = []

    # passengers which have been picked up
    passengers: set[Passenger] = set()

    # gets reset whenever the bus crashes
    created_at: int = 0

    # if not zero, the bus has crashed and you have to wait
    # until respawn_at tick is reached before you'll be a
    # asked to make a move
    respawn_at: int = 0


class Passenger(BaseModel, frozen=True):
    id: PassengerId
    value: int  # how many points the passenger is worth
    destination: Dest  # where they need to be dropped off


class Player(BaseModel, frozen=True):
    teamname: str
    slot: Slot
    is_staff_agent: bool


# pydantic can't roundtrip to json fields of type dict[tuple[int, int], ...]
# so we need to hack around this limitation by using a custom serializer and
# validator.
def pos_to_json(v: tuple[int, int]) -> str:
    x, y = v
    return f"{x}:{y}"


def json_to_pos(v: tuple[int, int] | str) -> tuple[int, int]:
    if isinstance(v, str):
        x, y = v.split(":", 1)
        return int(x), int(y)
    return v


Pos = Annotated[
    tuple[int, int], PlainSerializer(pos_to_json), BeforeValidator(json_to_pos)
]
