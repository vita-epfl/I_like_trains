from asyncio import StreamReader, StreamWriter
import asyncio
from typing import cast
import unittest
from common.config import ServerConfig
from common.messages import JoinRequest
from common.state import RoomChoice
from server.room import Room


class TestRoom(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        config = ServerConfig(room_max_wait_game_start_seconds=0.5)
        config.agents["test"] = "agent.py"
        config.seed = 1234
        self.room_choice = RoomChoice(total_players=2, min_staff_agents=0)
        maps = {"test": Room.load_map("test", "maps/map_test.txt")}
        self.room = Room(1, config, self.room_choice, maps)

    async def test_joining_room(self):
        # There's space for the first player
        p1 = await self.room.join(
            JoinRequest(teamname="player1", room_choice=self.room_choice),
            cast(StreamReader, None),
            cast(StreamWriter, None),
        )
        self.assertTrue(p1)
        # Hacky way of checking that self.room.wait_for_start() would block
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(self.room.wait_for_start(), 0.01)

        # There's space for the second player
        p2 = await self.room.join(
            JoinRequest(teamname="player2", room_choice=self.room_choice),
            cast(StreamReader, None),
            cast(StreamWriter, None),
        )
        self.assertTrue(p2)
        # Waiting on the room to start should no longer block
        await asyncio.wait_for(self.room.wait_for_start(), 0.01)

        # No more space for third player
        p3 = await self.room.join(
            JoinRequest(teamname="player3", room_choice=self.room_choice),
            cast(StreamReader, None),
            cast(StreamWriter, None),
        )
        self.assertFalse(p3)

    async def test_room_gets_agents(self):
        # First player joins
        p1 = await self.room.join(
            JoinRequest(teamname="player1", room_choice=self.room_choice),
            cast(StreamReader, None),
            cast(StreamWriter, None),
        )
        self.assertTrue(p1)

        # The room eventually starts
        await self.room.wait_for_start()
        self.assertEqual(len(self.room.local_agents), 1)

        # Player 2 won't be able to join
        p2 = await self.room.join(
            JoinRequest(teamname="player2", room_choice=self.room_choice),
            cast(StreamReader, None),
            cast(StreamWriter, None),
        )
        self.assertFalse(p2)
