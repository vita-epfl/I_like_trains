import asyncio
import importlib
import logging

from client.renderer import ConnectionState, Renderer
from common.base_agent import AgentWithKey, BaseAgent
from common.config import Config
from common.messages import (
    GameUpdate,
    JoinRequest,
    Message,
    Move,
    MoveRequest,
    RoomUpdate,
)

logger = logging.getLogger("client")


class Client:
    def __init__(self, config: Config) -> None:
        self.config = config.client
        self.agent: BaseAgent | None = None
        self.renderer = Renderer(self.config)

    async def run(self) -> None:
        asyncio.create_task(self.network())
        await self.renderer.run_event_loop()

    async def network(self) -> None:
        writer: asyncio.StreamWriter | None = None
        try:
            connect_to = self.config.connect_to
            port = self.config.port
            reader, writer = await asyncio.open_connection(connect_to, port)
            await self._network(reader, writer)
        finally:
            if writer is not None:
                writer.close()
            self.renderer.connection_state = ConnectionState.DISCONNECTED

    async def _network(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        # Connect to server and process incoming messages
        # We return when the server disconnects.
        logger.info(f"connecting to server {self.config.connect_to}:{self.config.port}")
        join_message = Message(
            join=JoinRequest(
                teamname=self.config.teamname,
                room_choice=self.config.room_choice,
            ),
        )
        await join_message.send(writer)

        while True:
            response = await Message.recv(reader)
            if response is None:
                writer.close()
                return
            self.renderer.connection_state = ConnectionState.CONNECTED
            if response.room_update is not None:
                if self.agent is None:
                    self.agent = self.load_agent(response.room_update)

                self.renderer.update_room_state(
                    response.room_update.slot, response.room_update.room_state
                )
                self.agent.room_state = response.room_update.room_state
                if self.agent.slot != response.room_update.slot:
                    logger.error("server changed out slot (should never happen)")
                self.agent.slot = response.room_update.slot
            if response.game_update is not None:
                move = await self.process_game_update(response.game_update)
                if response.game_update.move_expected:
                    move_message = Message(
                        move=MoveRequest(
                            move=move, tick=response.game_update.game_state.tick
                        )
                    )
                    await move_message.send(writer)

    def load_agent(self, room_update: RoomUpdate) -> BaseAgent:
        # Load agent
        logger.info(f"loading agent: {self.config.agent_filename}")
        agent_file_name = self.config.agent_filename.removesuffix(".py")

        # Construct the module path correctly
        module_path = f"common.agents.{agent_file_name}"
        logger.info(f"importing module: {module_path}")

        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as e:
            logger.error(
                f"Agent file '{agent_file_name}' not found in common/agents/ folder. Check your config.json."
            )
            raise e

        agent = module.Agent(room_update.room_state, room_update.slot)
        if isinstance(agent, AgentWithKey):
            self.renderer.key_event = agent.key_event
        return agent

    async def process_game_update(self, game_update: GameUpdate) -> Move:
        if self.renderer.game_state is not None:
            if self.renderer.game_state.tick >= game_update.game_state.tick:
                logger.error(
                    f"received a stale state (should never happen) {self.renderer.game_state.tick} >= {game_update.game_state.tick}"
                )
                return Move()
        self.renderer.game_state = game_update.game_state
        if self.agent is None:
            logger.error(
                "received game update before room update (should never happen)"
            )
            return Move()
        if game_update.move_expected:
            try:
                if self.config.agent_timeout_seconds > 0:
                    move = await asyncio.wait_for(
                        self.agent.async_get_move(game_update.game_state),
                        timeout=self.config.agent_timeout_seconds,
                    )
                    return move
                else:
                    move = await self.agent.async_get_move(game_update.game_state)
                    return move
            except TimeoutError:
                if not isinstance(self.agent, AgentWithKey):
                    # When using a keyboard, we know that we are slow, no point
                    # filling the logs.
                    logger.error("get_move() timed out, your agent is too slow!")
                return Move()
            except Exception as e:
                logger.exception(e)
                logger.error("Agent raised an exception")
                return Move()
        return Move()
