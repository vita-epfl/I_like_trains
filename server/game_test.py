import unittest
import random
from common.config import ServerConfig
from common.messages import Dir
from common.state import Passenger, Player, RoomChoice, RoomState
from server.game import Game
from server.room import Room


class TestGame(unittest.TestCase):
    def setUp(self) -> None:
        self.random = random.Random(1234)
        config = ServerConfig()
        config.maps["test"] = "maps/map_test.txt"
        player1 = Player(teamname="p1", slot=0, is_staff_agent=False)
        player2 = Player(teamname="p2", slot=1, is_staff_agent=False)
        map = Room.load_map(config=config, rng=self.random, name="test")
        self.room_state = RoomState(
            players={player1, player2},
            room_choice=RoomChoice(),
            created_at=0,
            room_max_wait_game_start_seconds=10,
            game_duration_ticks=100,
            desired_passengers=1,
            respawn_ticks=10,
            bus_length=2,
            max_passengers=1,
            spawn_passenger_away_from_bus_distance=0,
            drop_passenger_from_bus_distance=0,
            passenger_values={13},
            passenger_pickup_from_bus_distance=0,
            map=map,
        )
        self.game = Game(self.random, self.room_state, 1)
        self.passenger1 = Passenger(id=1, value=13, destination="A")

    def test_neighboring_cells(self) -> None:
        p = (0, 0)
        for i in range(10):
            cells = Game.neighboring_cells(p, i)
            self.assertEqual(len(cells), (i * 2 + 1) * (i * 2 + 1))
            for x, y in cells:
                self.assertTrue(abs(x) <= i, x)
                self.assertTrue(abs(y) <= i, x)

    def test_game(self) -> None:
        # Since the rng is fixed, we know the game is in the following state:
        # 1 1 . . A
        # . 2 2 . .
        # . a . . .

        # Verify consistency of game.game_state.buses and game.buses
        self.assertEqual(self.game.game_state.buses[0].positions, [(0, 0), (1, 0)])
        self.assertEqual(self.game.buses[(0, 0)], self.game.game_state.buses[0])
        self.assertEqual(self.game.buses[(1, 0)], self.game.game_state.buses[0])

        self.assertEqual(self.game.game_state.buses[1].positions, [(1, 1), (2, 1)])
        self.assertEqual(self.game.buses[(1, 1)], self.game.game_state.buses[1])
        self.assertEqual(self.game.buses[(2, 1)], self.game.game_state.buses[1])

        # Verify consistency of game.passengers and game.game_state.passengers
        self.assertEqual(self.game.game_state.passengers[(1, 2)].id, 1)
        self.assertEqual(self.game.passengers[1], (1, 2))

    def test_crashing_by_going_out_of_bounds(self):
        self.assertTrue(self.game.bus_is_alive(0))
        self.game.move_bus(0, Dir.LEFT)
        self.assertFalse(self.game.bus_is_alive(0))
        for _ in range(10):
            self.game.tick()
        self.assertTrue(self.game.bus_is_alive(0))

    def test_crashing_by_hitting_other_bus(self):
        self.assertTrue(self.game.bus_is_alive(0))
        self.game.move_bus(0, Dir.DOWN)
        self.game.move_bus(0, Dir.RIGHT)
        self.assertFalse(self.game.bus_is_alive(0))

    def test_pickup_passenger(self):
        # player 1 tries to pickup passenger 1 but is too far
        self.game.pickup(0, 1)
        self.assertEqual(self.game.game_state.buses[0].passengers, set())

        # player 2 moves and picks up passenger 1
        self.game.move_bus(1, Dir.DOWN)
        self.game.pickup(1, 1)
        self.assertIsNone(self.game.game_state.passengers.get((1, 2)))
        self.assertIsNone(self.game.passengers.get(1))
        self.assertEqual(self.game.game_state.buses[1].passengers, {self.passenger1})

        # player 1 tries to pickup same passenger
        self.game.pickup(0, 1)
        self.assertEqual(self.game.game_state.buses[0].passengers, set())

    def test_drop_passenger(self):
        # player 2 moves and picks up passenger 1
        self.game.move_bus(1, Dir.DOWN)
        self.game.pickup(1, 1)

        # player 1 attempts to drop a passenge they aren't carrying
        self.game.drop(0, 1, False)
        self.assertEqual(len(self.game.game_state.passengers), 0)
        self.assertEqual(len(self.game.passengers), 0)
        self.assertEqual(self.game.game_state.buses[1].passengers, {self.passenger1})

        # player 2 drops passenger 1
        self.game.drop(1, 1, False)
        self.assertEqual(self.game.game_state.passengers[(1, 2)].id, 1)
        self.assertEqual(self.game.passengers[1], (1, 2))
        self.assertEqual(self.game.game_state.buses[1].passengers, set())

    def test_drop_passenger_at_destination(self):
        self.game.move_bus(1, Dir.DOWN)
        self.game.pickup(1, 1)
        self.game.move_bus(1, Dir.RIGHT)
        self.game.move_bus(1, Dir.RIGHT)
        self.game.move_bus(1, Dir.RIGHT)
        self.game.move_bus(1, Dir.UP)
        self.game.move_bus(1, Dir.UP)
        self.game.drop(1, 1, False)
        # passenger 2 is spawned
        self.assertEqual(self.game.game_state.passengers[(0, 2)].id, 2)
        self.assertEqual(self.game.passengers[2], (0, 2))
        self.assertEqual(self.game.game_state.buses[1].passengers, set())
        self.assertEqual(self.game.game_state.scores[1], 13)

    def test_crashing_with_passengers(self):
        self.game.move_bus(1, Dir.DOWN)
        self.game.pickup(1, 1)
        self.game.move_bus(1, Dir.LEFT)
        self.game.move_bus(1, Dir.UP)
        self.game.move_bus(1, Dir.UP)
        self.assertFalse(self.game.bus_is_alive(1))
        self.assertEqual(self.game.game_state.passengers[(0, 2)], self.passenger1)
        self.assertEqual(self.game.passengers[1], (0, 2))
