import asyncio
import importlib
import logging

from client.renderer import ConnectionState, Renderer
from common.base_agent import AgentWithKey, BaseAgent
from common.config import ClientConfig
from common.config import Config
from common.messages import GameUpdate, JoinRequest, Message, Move, MoveRequest

logger = logging.getLogger("client")


class Client:
    def __init__(self, config: Config) -> None:
        self.config: ClientConfig = config.client

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

        self.agent: BaseAgent = module.Agent()
        key_event = None
        if isinstance(self.agent, AgentWithKey):
            key_event = self.agent.key_event
        self.renderer = Renderer(self.config, key_event)

    async def run(self) -> None:
        asyncio.create_task(self.network())
        await self.renderer.run_event_loop()

    async def network(self) -> None:
        try:
            await self._network()
        finally:
            self.renderer.connection_state = ConnectionState.DISCONNECTED

    async def _network(self) -> None:
        # Connect to server and process incoming messages
        # We return when the server disconnects.
        logger.info(f"connecting to server {self.config.connect_to}:{self.config.port}")
        reader, writer = await asyncio.open_connection(
            self.config.connect_to, self.config.port
        )
        join_message = Message(
            join=JoinRequest(
                teamname=self.agent.teamname(),
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
                self.renderer.update_room_state(
                    response.room_update.slot, response.room_update.room_state
                )
                self.agent.room_state = response.room_update.room_state
                assert (self.agent.slot is None) or (
                    self.agent.slot == response.room_update.slot
                )
                self.agent.slot = response.room_update.slot
            if response.game_update is not None:
                move = await self.process_game_update(response.game_update)
                if move is not None:
                    move_message = Message(
                        move=MoveRequest(
                            move=move, tick=response.game_update.game_state.tick
                        )
                    )
                    await move_message.send(writer)

    async def process_game_update(self, game_update: GameUpdate) -> Move | None:
        if self.renderer.game_state is not None:
            if self.renderer.game_state.tick >= game_update.game_state.tick:
                logger.error(
                    f"received a stale state {self.renderer.game_state.tick} >= {game_update.game_state.tick}"
                )
                if game_update.move_expected:
                    return Move()
                return None
        self.renderer.game_state = game_update.game_state
        if game_update.move_expected:
            try:
                assert self.renderer.room_state is not None
                if not self.renderer.room_state.room_choice.slow:
                    move = await asyncio.wait_for(
                        self.agent.async_get_move(game_update.game_state),
                        timeout=self.config.agent_timeout_seconds,
                    )
                else:
                    move = await self.agent.async_get_move(game_update.game_state)
                return move
            except TimeoutError:
                logger.error("get_move() timed out, your agent is too slow!")
                return Move()
        return None
