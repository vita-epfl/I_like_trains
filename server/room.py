import asyncio
import datetime
import importlib
import logging
import math
import random
from asyncio import StreamReader, StreamWriter
from typing import Awaitable

from common.base_agent import BaseAgent
from common.config import ServerConfig
from common.messages import GameUpdate, JoinRequest, Message, Move, RoomUpdate
from common.state import Dest, GameState, Map, Player, Pos, RoomChoice, RoomState, Slot
from server.game import Game

logger = logging.getLogger("server.room")

# Room code handles connections to the client and contains
# an instance of a Game.
#
# Also handles waiting for the room to fill up or time to elapse prior
# to starting the game.
#
# The code assumes it's always running on the same thread so doesn't use any locks. This decision
# should be fine since the game is I/O heavy and the bottleneck is probably
# the network layer.
#
# In order to decide when to start a room, the following logic is implemented:
# - the asyncio task handling the first player to join a room waits on a combination
#   of asyncio.Event and a timeout.
# - other asyncio tasks handle subsequent players who join the room. Those tasks terminate right away.
# - the asyncio task which handles the last player to join the room signals to the first task that the room
#   is ready to start and terminates.
# - the first task then runs the room.
# - if the last player never joins the room, the timeout also trigger the first task to run the room.


class Room:
    def __init__(
        self,
        room_id: int,
        config: ServerConfig,
        room_choice: RoomChoice,
        maps: dict[str, Map],
    ) -> None:
        self.room_id = room_id  # for debugging purpose
        self.config = config
        logger.info(f"#{room_id} creating: {room_choice}")

        seed = config.seed
        if seed is None:
            seed = random.randint(1, 9999)
        self.random = random.Random(seed)
        self.created_at = datetime.datetime.now()

        map = None
        if room_choice.map_choice is not None:
            map = maps.get(room_choice.map_choice)
        if map is None:
            map = random.choice(list(maps.values()))

        self.room_state = RoomState(
            players=set(),
            room_choice=room_choice,
            created_at=math.floor(self.created_at.timestamp()),
            room_max_wait_game_start_seconds=config.room_max_wait_game_start_seconds,
            game_duration_ticks=config.game_duration_ticks * room_choice.total_players,
            desired_passengers=config.desired_passengers,
            respawn_ticks=config.respawn_ticks * room_choice.total_players,
            bus_length=self.random.randint(
                config.bus_min_length, config.bus_max_length
            ),
            max_passengers=config.max_passengers,
            spawn_passenger_away_from_bus_distance=config.spawn_passenger_away_from_bus_distance,
            drop_passenger_from_bus_distance=config.drop_passenger_from_bus_distance,
            passenger_values=config.passenger_values,
            passenger_pickup_from_bus_distance=config.passenger_pickup_from_bus_distance,
            map=map,
        )
        self.streams: dict[Slot, tuple[StreamReader, StreamWriter]] = {}
        self.local_agents: dict[Slot, BaseAgent] = {}

        self.available_slots: list[Slot] = list(
            range(self.room_state.room_choice.total_players)
        )
        self.random.shuffle(self.available_slots)

        self.full_event = asyncio.Event()  # set when the room is full

    async def join(
        self,
        join_request: JoinRequest,
        reader: StreamReader,
        writer: StreamWriter,
    ) -> bool:
        """
        Joins the room. Returns False if the room is full.
        """
        assert join_request.room_choice == self.room_state.room_choice
        if self.is_full():
            return False
        slot = self.available_slots.pop()
        logger.info(f"#{self.room_id} joined: {join_request.teamname}:{slot}")
        player = Player(teamname=join_request.teamname, slot=slot, is_staff_agent=False)
        self.room_state.players.add(player)
        self.streams[slot] = (reader, writer)
        await self.notify_all(True, None, None)
        if self.is_full():
            self.full_event.set()
        return True

    def is_full(self) -> bool:
        players = len(self.room_state.players)
        total = self.room_state.room_choice.total_players
        min_staff_agents = self.room_state.room_choice.min_staff_agents
        return players >= total - min_staff_agents

    async def notify_all(
        self,
        room_state: bool,
        game_state: GameState | None,
        except_slot: Slot | None,
    ) -> None:
        promises: list[Awaitable[None]] = []
        for slot, (_, writer) in self.streams.items():
            if slot == except_slot:
                continue
            room_update = None
            if room_state:
                room_update = RoomUpdate(slot=slot, room_state=self.room_state)
            game_update = None
            if game_state is not None:
                game_update = GameUpdate(game_state=game_state, move_expected=False)
            msg = Message(room_update=room_update, game_update=game_update)
            promises.append(msg.send(writer))
        await asyncio.gather(*promises)

    async def wait_for_start(self) -> None:
        """
        Returns after enough players are in the room or some amount of time has elapsed.
        """
        try:
            t = self.config.room_max_wait_game_start_seconds
            await asyncio.wait_for(self.full_event.wait(), t)
            logger.info(f"#{self.room_id} ready to start (enough players)")
        except TimeoutError:
            logger.info(f"#{self.room_id} ready to start (elapsed)")

        should_notify = False
        total_players = self.room_state.room_choice.total_players
        while len(self.room_state.players) < total_players:
            self.add_agent()
            should_notify = True
        if should_notify:
            await self.notify_all(True, None, None)

    def add_agent(self):
        agent_name = self.random.choice(list(self.config.agents.keys()))
        agent_file_name = self.config.agents[agent_name]

        logger.info(
            f"#{self.room_id} adding agent: {agent_name} from {agent_file_name}"
        )
        agent_file_name = agent_file_name.removesuffix(".py")
        module_path = f"common.agents.{agent_file_name}"
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as e:
            logger.error(
                f"#{self.room_id} agent file {agent_file_name} not found in common/agents/ folder. Check your config.json."
            )
            raise e

        slot = self.available_slots.pop()
        agent: BaseAgent = module.Agent(self.room_state, slot)
        logger.info(f"#{self.room_id} added: {agent_name}:{slot}")
        player = Player(teamname=agent_name, slot=slot, is_staff_agent=True)
        self.room_state.players.add(player)
        self.local_agents[slot] = agent
        agent.slot = slot
        agent.room_state = self.room_state

    async def run(self) -> dict[Slot, int]:
        game = Game(self.random, self.room_state, self.room_id)
        while True:
            done = await self.tick(game)
            if done:
                for _, writer in self.streams.values():
                    writer.close()
                return game.game_state.scores

    async def tick(self, game: Game) -> bool:
        slot = game.tick()
        if len(self.streams) == 0:
            # all the clients have disconnected
            # end the game
            return True
        if slot is None:
            # the game is done
            await self.notify_all(False, game.game_state, None)
            return True
        await self.notify_all(False, game.game_state, slot)

        if not game.bus_is_alive(slot):
            # It's the player's turn but their bus has crashed so
            # there's nothing to do.
            return False

        if slot in self.local_agents:
            # It's the local agent's turn to move
            move = Move()
            try:
                move = await asyncio.wait_for(
                    self.local_agents[slot].async_get_move(game.game_state),
                    self.config.local_agent_timeout_seconds,
                )
            except TimeoutError:
                logger.error(f"#{game.room_id} {slot} local agent timeout")
            except Exception as e:
                logger.error(f"#{game.room_id} {slot} local agent exception: {e}")
            finally:
                game.move(slot, move)
        else:
            # It's the client's turn to move
            move = await self.get_move_from_client(game, slot)
            game.move(slot, move)
        return False

    async def get_move_from_client(self, game: Game, slot: Slot) -> Move:
        if slot not in self.streams:
            # client has disconnected, return an empty move
            return Move()
        reader, writer = self.streams[slot]
        game_update_message = Message(
            game_update=GameUpdate(game_state=game.game_state, move_expected=True)
        )
        await game_update_message.send(writer)
        response = await Message.recv(reader)
        if response is None:
            # We can't communicate with player, free up resources
            writer.close()
            del self.streams[slot]
            logger.debug(f"#{self.room_id} {slot} has disconnected")
            return Move()
        if response.move is None:
            logger.debug(f"#{self.room_id} {slot} sent incorrect message: {response}")
            # We got back an incorrect message
            return Move()
        if response.move.tick == game.game_state.tick:
            return response.move.move

        # Since we wait for a response, we should never get
        # an old message.
        logger.info(
            f"#{self.room_id} {slot} incorrect response.move.tick: {response.move.tick} vs {game.game_state.tick}"
        )
        return Move()

    @staticmethod
    def load_map(name: str, path: str) -> Map:
        available_cells: set[Pos] = set()
        delivery_zones: dict[Pos, Dest] = {}
        width = 0
        height = 0
        with open(path, "r") as f:
            # figure out the grid size
            for j, line in enumerate(f):
                height = j
                for i, c in enumerate(line.rstrip()):
                    width = max(width, i)
                    if c == "#":
                        continue
                    available_cells.add((i, j))
                    if c != ".":
                        delivery_zones[(i, j)] = c
        return Map(
            name=name,
            width=width + 1,
            height=height + 1,
            available_cells=available_cells,
            delivery_zones=delivery_zones,
        )
