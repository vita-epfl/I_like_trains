import logging
import random

from common.messages import Dir, Move
from common.state import Bus, GameState, Passenger, PassengerId, Pos, RoomState, Slot

logger = logging.getLogger("server.game")


class Game:
    """
    A game represents the game at the logical level. The following code lives here:
    - code to move a bus
    - code to check if a bus collided
    - code to check if a bus is allowed to pickup a given passenger
    - code to drop off a passenger and increment the player's score if needed
    - code to spawn a bus
    - code to spawn a passenger

    The code keeps its state in GameState, which gets sent to the client. Some additional
    state, such as self.buses and self.passengers is stored here to improve efficiency.
    """

    def __init__(self, rng: random.Random, room_state: RoomState, room_id: int):
        self.random = rng
        self.room_state = room_state
        self.room_id = room_id
        self.game_state = GameState()

        self.buses: dict[Pos, Bus] = {}  # for quick lookup
        self.passengers: dict[PassengerId, Pos] = {}  # for quick lookup

        self.available_cells = list(room_state.map.available_cells)
        self.next_passenger_id: PassengerId = 1
        self.destinations = set(room_state.map.delivery_zones.values())
        for player in self.room_state.players:
            self.spawn_bus(player.slot)
        for _ in range(self.room_state.desired_passengers):
            self.spawn_passenger()
        self.game_state.scores = {}

    @staticmethod
    def neighboring_cells(pos: Pos, n: int) -> set[Pos]:
        r: set[Pos] = set()
        x, y = pos
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                r.add((x + i, y + j))
        return r

    def update_passengers(self, passenger: Passenger, pos: Pos) -> None:
        self.game_state.passengers[pos] = passenger
        self.passengers[passenger.id] = pos

    def remove_passengers(self, passenger: Passenger, pos: Pos) -> None:
        del self.game_state.passengers[pos]
        del self.passengers[passenger.id]

    def spawn_passenger(self) -> None:
        """
        Spawns a passenger. Looks for a position which isn't
        occupied by any existing passengers. Tries to pick
        cells away from existing buses.
        """
        available_cells = self.room_state.map.available_cells.copy()
        for pos in self.game_state.passengers:
            # Remove cells which have passengers
            available_cells.remove(pos)

        slots = list(range(self.room_state.room_choice.total_players))
        self.random.shuffle(slots)
        for slot in slots:
            # Remove cells which are close to buses, unless we run out of
            # cells to remove. Iterate in random slot order for fairness purpose.
            bus = self.game_state.buses[slot]
            if len(bus.positions) > 0:
                for p in Game.neighboring_cells(
                    bus.positions[0],
                    self.room_state.spawn_passenger_away_from_bus_distance,
                ):
                    if len(available_cells) > 1:
                        available_cells.discard(p)
        pos = self.random.choice(list(available_cells))
        value = self.random.choice(list(self.room_state.passenger_values))
        destinations = self.destinations.copy()
        if pos in self.room_state.map.delivery_zones:
            destinations.remove(self.room_state.map.delivery_zones[pos])
        destination = self.random.choice(list(destinations))

        new_passenger = Passenger(
            id=self.next_passenger_id, value=value, destination=destination
        )
        self.next_passenger_id += 1
        self.update_passengers(new_passenger, pos)

    def spawn_bus(self, slot: Slot):
        positions = self.spawn_bus_recursive(slot)
        bus = Bus(positions=positions, created_at=self.game_state.tick)
        for p in positions:
            self.buses[p] = bus
        self.game_state.buses[slot] = bus

    def spawn_bus_recursive(self, slot: Slot) -> list[Pos]:
        """
        Go through every valid position for the front of the bus
        and try to build a bus.

        This method can potentially take a bunch of time. The best
        way to keep it fast is to ensure that maps are large enough.
        """
        self.random.shuffle(self.available_cells)
        for x, y in self.available_cells:
            p: list[Pos] = list()
            if self._spawn_bus_recursive(x, y, p, self.room_state.bus_length):
                return p

        # If we get here, it means the map is too small for the number
        # of buses or that we have some serious bug
        assert False

    def _spawn_bus_recursive(
        self, x: int, y: int, partial_bus: list[Pos], length: int
    ) -> bool:
        """
        Recursively extend the partial bus.
        """
        if length == 0:
            # We are done
            return True

        if (x, y) not in self.room_state.map.available_cells:
            # We encountered a wall
            return False

        if (x, y) in self.buses:
            # We encountered another bus
            return False

        if (x, y) in partial_bus:
            # We encountered our current bus
            return False
        partial_bus.append((x, y))
        if (
            self._spawn_bus_recursive(x + 1, y, partial_bus, length - 1)
            or self._spawn_bus_recursive(x - 1, y, partial_bus, length - 1)
            or self._spawn_bus_recursive(x, y + 1, partial_bus, length - 1)
            or self._spawn_bus_recursive(x, y - 1, partial_bus, length - 1)
        ):
            # One of the disjunctions passed, we are done
            return True

        # Revert change to partial_bus and try creating the bus differently
        partial_bus.pop()
        return False

    def tick(self) -> Slot | None:
        """
        Increments the game state tick and returns the slot number of the player who gets to move.
        Returns None when the game ends.
        """
        self.game_state.tick += 1
        if self.game_state.tick >= self.room_state.game_duration_ticks:
            return None
        return self.game_state.tick % self.room_state.room_choice.total_players

    def should_move(self, slot: Slot) -> bool:
        bus = self.game_state.buses[slot]
        if bus.respawn_at > 0:
            if self.game_state.tick < bus.respawn_at:
                # bus has crashed, they don't get to move yet
                return False
            self.spawn_bus(slot)
        return True

    def move(self, slot: Slot, move: Move) -> None:
        for passenger_id in move.drop:
            self.drop(slot, passenger_id)
        if move.direction is not None:
            self.move_bus(slot, move.direction)
        for passenger_id in move.pickup:
            self.pickup(slot, passenger_id)

    def pickup(self, slot: Slot, passenger_id: PassengerId) -> None:
        pos = self.passengers.get(passenger_id)
        if pos is None:
            # Can't pickup passenger which isn't available
            return

        bus = self.game_state.buses[slot]
        if bus.respawn_at > 0:
            # Can't pickup if we crashed. This can happen if the current move
            # crashed due to the order in which we process the move
            return
        bus_x, bus_y = bus.positions[0]
        passenger_x, passenger_y = pos
        d = self.room_state.passenger_pickup_from_bus_distance
        if abs(bus_x - passenger_x) > d or abs(bus_y - passenger_y) > d:
            # attempting to pickup passenger not located nearby
            return

        if len(bus.passengers) >= self.room_state.max_passengers:
            # the bus is full
            return

        passenger = self.game_state.passengers[pos]
        assert passenger_id == passenger.id
        self.remove_passengers(passenger, pos)

        self.game_state.buses[slot].passengers.add(passenger)
        logger.debug(
            f"#{self.room_id} {self.get_player(slot)}:{slot} picked up passenger {passenger_id}"
        )

    def drop(self, slot: Slot, passenger_id: int) -> None:
        """
        Rules for dropping passengers:
        - passenger_id must be on a bus
        - the bus must belong to slot
        - if the bus's front is on the correct delivery zone
          - the passenger is dropped off and the player's score is incremented
        - otherwise, if the bus's front is not occupied by another passenger
          - the passenger is dropped off
        """
        bus = self.game_state.buses[slot]
        passenger = None
        for p in bus.passengers:
            if p.id == passenger_id:
                passenger = p
                break
        if passenger is None:
            # player attempted to drop passenger they aren't carrying
            return

        bus.passengers.remove(passenger)
        pos = bus.positions[0]
        d = self.room_state.map.delivery_zones.get(pos)
        if d == passenger.destination:
            self.game_state.scores[slot] = (
                self.game_state.scores.get(slot, 0) + passenger.value
            )
            logger.debug(
                f"#{self.room_id} {self.get_player(slot)}:{slot} dropped {passenger_id} ({passenger.value}) at their destination, new score: {self.game_state.scores[slot]}"
            )
            self.spawn_passenger()
        else:
            # Use the same logic as crash() to find a spot to drop off passenger
            # TODO(alok): reduce copy-pasta
            preferred_locations: set[Pos] = set()
            for pos in bus.positions:
                preferred_locations |= Game.neighboring_cells(
                    pos, self.room_state.drop_passenger_from_bus_distance
                )
            preferred_locations &= self.room_state.map.available_cells
            preferred_locations = (
                preferred_locations - self.game_state.passengers.keys()
            )
            locations = list(preferred_locations)
            self.random.shuffle(locations)
            if len(locations) > 0:
                # We found a spot for this passenger
                p = locations.pop()
                self.update_passengers(passenger, p)
            else:
                # We failed to find a spot for this passenger, respawn a new passenger
                self.spawn_passenger()

    def move_bus(self, slot: Slot, direction: Dir) -> None:
        bus = self.game_state.buses[slot]
        x, y = bus.positions[0]
        dx = 0
        dy = 0
        match direction:
            case Dir.UP:
                dy = -1
            case Dir.RIGHT:
                dx = 1
            case Dir.DOWN:
                dy = 1
            case Dir.LEFT:
                dx = -1
        new_x = x + dx
        new_y = y + dy
        new_pos = (new_x, new_y)
        crashed = False
        if new_pos not in self.room_state.map.available_cells:
            crashed = True
        elif (
            new_x < 0
            or new_y < 0
            or new_x >= self.room_state.map.width
            or new_y >= self.room_state.map.height
        ):
            crashed = True
        if new_pos in self.buses:
            crashed = True
        if crashed:
            self.crashed(slot, new_x, new_y)
            return
        del self.buses[bus.positions[-1]]
        self.buses[new_pos] = bus
        for i in range(len(bus.positions) - 1, 0, -1):
            bus.positions[i] = bus.positions[i - 1]
        bus.positions[0] = new_pos

    def crashed(self, slot: int, new_x: int, new_y: int):
        logger.debug(
            f"#{self.room_id} {self.get_player(slot)}:{slot} crashed their bus ({new_x}, {new_y})"
        )
        bus = self.game_state.buses[slot]
        bus.respawn_at = self.game_state.tick + self.room_state.respawn_ticks

        preferred_locations: set[Pos] = set()
        for pos in bus.positions:
            preferred_locations |= Game.neighboring_cells(
                pos, self.room_state.drop_passenger_from_bus_distance
            )
            del self.buses[pos]
        bus.positions = []

        preferred_locations &= self.room_state.map.available_cells
        preferred_locations = preferred_locations - self.game_state.passengers.keys()
        locations = list(preferred_locations)
        self.random.shuffle(locations)
        for passenger in bus.passengers:
            if len(locations) > 0:
                # we found a spot for this passenger
                p = locations.pop()
                self.update_passengers(passenger, p)
            else:
                # We failed to find a spot for this passenger.
                # Respawn a new passenger.
                self.spawn_passenger()
        bus.passengers = set()

    def get_player(self, slot: int) -> str:
        for player in self.room_state.players:
            if player.slot == slot:
                return player.teamname
        return "?"
