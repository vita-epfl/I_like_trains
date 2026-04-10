import asyncio
import logging
import os
import random
import urllib.request
from urllib.error import URLError

from common.config import Config
from common.messages import JoinRequest, Message
from common.state import RoomChoice
from server.room import Room

logger = logging.getLogger("server")


class Server:
    def __init__(self, config: Config):
        """
        Checks server config is valid
        """
        self.config = config.server
        # set a random seed if it's 0
        if self.config.seed == 0:
            self.config.seed = random.randint(1, 9999)
        logger.debug(self.config)
        self.verify_agent_files()

        self.rng = random.Random(self.config.seed)

        # Rooms which are either running or waiting to be filled up
        self.latest_rooms: dict[RoomChoice, Room] = {}
        self.next_room_id = 1

    async def run(self):
        host = "127.0.0.1"
        if not self.config.localhost_only:
            host = "0.0.0.0"
            logger.info(
                f"server might be reachable via public IP: {self.get_public_ip()}"
            )
        logger.info(f"starting server on {host}:{self.config.port}")
        server = await asyncio.start_server(
            self.handle_messages, host, self.config.port
        )
        async with server:
            await server.serve_forever()

    async def handle_messages(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        msg = await Message.recv(reader)
        if msg is None:
            return
        if msg.join is None:
            addr = writer.get_extra_info("peername")
            logger.info(f"Received wrong message from {addr}, ignoring")
            return

        join_request = msg.join

        # Limit min_staff_agents to total_players - 1 since we
        # aren't interested to play against ourselves.
        min_staff_agents = join_request.room_choice.min_staff_agents
        if min_staff_agents >= join_request.room_choice.total_players:
            join_request.room_choice = RoomChoice(
                slow=join_request.room_choice.slow,
                total_players=join_request.room_choice.total_players,
                min_staff_agents=join_request.room_choice.total_players - 1,
                map_choice=join_request.room_choice.map_choice,
            )

        # Fix map_choice it's wrong
        if (
            join_request.room_choice.map_choice is not None
            and join_request.room_choice.map_choice not in self.config.maps
        ):
            join_request.room_choice = RoomChoice(
                slow=join_request.room_choice.slow,
                total_players=join_request.room_choice.total_players,
                min_staff_agents=join_request.room_choice.min_staff_agents,
                map_choice=None,
            )

        # Either join an existing room or create a new room
        await self.join_or_create_room(join_request, reader, writer)

    async def join_or_create_room(
        self,
        join_request: JoinRequest,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        room_creator = False
        room = self.latest_rooms.get(join_request.room_choice)
        if room is not None:
            try_joining = await room.join(join_request, reader, writer)
            if not try_joining:
                room = None
        if room is None:
            # Create a new room
            room = Room(
                self.next_room_id,
                self.config,
                self.rng,
                join_request.room_choice,
            )
            self.next_room_id += 1
            self.latest_rooms[join_request.room_choice] = room
            room_creator = True
            try_joining = await room.join(join_request, reader, writer)
            # joining a room we just created should never fail
            assert try_joining
        if room_creator:
            await room.wait_for_start()
            result = await room.run()
            logger.info(f"#{room.room_id} game over. Results: {result}")
            # TODO(alok): save results to database

    def verify_agent_files(self):
        """
        Verifies that all agent files specified in the configuration exist in the common/agents directory.
        Raises an error and exits the server if any file is missing.
        """

        agents_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "common",
            "agents",
        )

        for agent_file_name in self.config.agents:
            agent_file_path = os.path.join(agents_dir, agent_file_name)
            if not os.path.exists(agent_file_path):
                error_msg = f"Agent file not found: {agent_file_name}"
                logger.error(error_msg)
                print(f"ERROR: {error_msg}")
                print(f"The file should be located at: {agent_file_path}")
                print("Server is shutting down.")
                raise FileNotFoundError(f"Missing agent file: {agent_file_path}")

        logger.info("All agent files verified successfully")

    def get_public_ip(self) -> str | None:
        """
        Gets the public IP address of this server using an external service
        """
        url = "https://api.ipify.org"
        try:
            with urllib.request.urlopen(url) as response:
                ip = response.read().decode("utf-8")
                return ip
        except URLError as e:
            logger.warning(f"failed to determine public IP ({url})")
            logger.info(e)
            return None
