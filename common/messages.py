"""
Pydantic models for all network messages in the I Like Trains game.

This module defines typed message models for serialization/deserialization
of JSON messages between client and server.

Message Types:
    - Server -> Client: state, game_started_success, spawn_success, respawn_failed,
                        death, game_over, waiting_room, initial_state, ping, pong,
                        disconnect, name_check, sciper_check, join_success,
                        drop_wagon_success, drop_wagon_failed, leaderboard, error
    - Client -> Server: agent_ids, ping, pong, direction, respawn, drop_wagon,
                        check_name, check_sciper
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel


# =============================================================================
# Enums for message types
# =============================================================================

class ServerMessageType(str, Enum):
    """Types of messages sent from server to client."""
    STATE = "state"
    GAME_STARTED_SUCCESS = "game_started_success"
    SPAWN_SUCCESS = "spawn_success"
    RESPAWN_FAILED = "respawn_failed"
    DEATH = "death"
    GAME_OVER = "game_over"
    WAITING_ROOM = "waiting_room"
    INITIAL_STATE = "initial_state"
    PING = "ping"
    PONG = "pong"
    DISCONNECT = "disconnect"
    NAME_CHECK = "name_check"
    SCIPER_CHECK = "sciper_check"
    JOIN_SUCCESS = "join_success"
    DROP_WAGON_SUCCESS = "drop_wagon_success"
    DROP_WAGON_FAILED = "drop_wagon_failed"
    LEADERBOARD = "leaderboard"
    GAME_STATUS = "game_status"
    BEST_SCORE = "best_score"
    ERROR = "error"


class ClientMessageType(str, Enum):
    """Types of messages sent from client to server."""
    AGENT_IDS = "agent_ids"
    PING = "ping"
    PONG = "pong"


class ClientActionType(str, Enum):
    """Types of actions sent from client to server."""
    DIRECTION = "direction"
    RESPAWN = "respawn"
    DROP_WAGON = "drop_wagon"
    CHECK_NAME = "check_name"
    CHECK_SCIPER = "check_sciper"


# =============================================================================
# Data models for nested structures
# =============================================================================

class TrainData(BaseModel):
    """Data structure for a train."""
    position: tuple[int, int] | None = None
    direction: tuple[int, int] | None = None
    wagons: list[tuple[int, int]] | None = None
    color: tuple[int, int, int] | None = None
    score: int | None = None
    alive: bool | None = None
    speed: float | None = None


class PassengerData(BaseModel):
    """Data structure for a passenger."""
    position: tuple[int, int]
    value: int = 1


class DeliveryZoneData(BaseModel):
    """Data structure for the delivery zone."""
    position: tuple[int, int]
    width: int
    height: int


class SizeData(BaseModel):
    """Data structure for game size."""
    game_width: int
    game_height: int


class GameStateData(BaseModel):
    """Data structure for game state updates (can be partial)."""
    trains: dict[str, dict[str, Any]] | None = None
    passengers: list[dict[str, Any]] | None = None
    delivery_zone: dict[str, Any] | None = None
    size: SizeData | None = None
    cell_size: int | None = None
    best_scores: dict[str, int] | None = None
    remaining_time: int | None = None
    rename_train: tuple[str, str] | None = None


class WaitingRoomData(BaseModel):
    """Data structure for waiting room information."""
    room_id: str
    players: list[str]
    nb_players: int
    game_started: bool
    waiting_time: int = 0


class InitialStateData(BaseModel):
    """Data structure for initial game state."""
    game_life_time: int
    start_time: float


class FinalScoreEntry(BaseModel):
    """Data structure for a final score entry."""
    name: str
    best_score: int


class GameOverData(BaseModel):
    """Data structure for game over information."""
    message: str
    final_scores: list[FinalScoreEntry]
    duration: int
    best_scores: dict[str, int]


# =============================================================================
# Server -> Client Messages
# =============================================================================

class StateMessage(BaseModel):
    """Game state update message."""
    type: Literal[ServerMessageType.STATE] = ServerMessageType.STATE
    data: dict[str, Any]

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class GameStartedSuccessMessage(BaseModel):
    """Message indicating the game has started."""
    type: Literal[ServerMessageType.GAME_STARTED_SUCCESS] = ServerMessageType.GAME_STARTED_SUCCESS

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class SpawnSuccessMessage(BaseModel):
    """Message indicating successful spawn."""
    type: Literal[ServerMessageType.SPAWN_SUCCESS] = ServerMessageType.SPAWN_SUCCESS
    nickname: str

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class RespawnFailedMessage(BaseModel):
    """Message indicating spawn failure."""
    type: Literal[ServerMessageType.RESPAWN_FAILED] = ServerMessageType.RESPAWN_FAILED
    message: str

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class DeathMessage(BaseModel):
    """Message indicating train death with cooldown."""
    type: Literal[ServerMessageType.DEATH] = ServerMessageType.DEATH
    remaining: float
    reason: str | None = None

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class GameOverMessage(BaseModel):
    """Message indicating game over with final scores."""
    type: Literal[ServerMessageType.GAME_OVER] = ServerMessageType.GAME_OVER
    data: GameOverData

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class WaitingRoomMessage(BaseModel):
    """Message with waiting room information."""
    type: Literal[ServerMessageType.WAITING_ROOM] = ServerMessageType.WAITING_ROOM
    data: WaitingRoomData

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class InitialStateMessage(BaseModel):
    """Message with initial game state."""
    type: Literal[ServerMessageType.INITIAL_STATE] = ServerMessageType.INITIAL_STATE
    data: InitialStateData

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class PingMessage(BaseModel):
    """Ping message for connection checking."""
    type: Literal[ServerMessageType.PING] = ServerMessageType.PING

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class PongMessage(BaseModel):
    """Pong response message."""
    type: Literal[ServerMessageType.PONG] = ServerMessageType.PONG

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class DisconnectMessage(BaseModel):
    """Message requesting client disconnect."""
    type: Literal[ServerMessageType.DISCONNECT] = ServerMessageType.DISCONNECT
    reason: str

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class NameCheckMessage(BaseModel):
    """Response to name availability check."""
    type: Literal[ServerMessageType.NAME_CHECK] = ServerMessageType.NAME_CHECK
    available: bool
    reason: str | None = None

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class SciperCheckMessage(BaseModel):
    """Response to sciper availability check."""
    type: Literal[ServerMessageType.SCIPER_CHECK] = ServerMessageType.SCIPER_CHECK
    available: bool

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class JoinSuccessMessage(BaseModel):
    """Message indicating successful join."""
    type: Literal[ServerMessageType.JOIN_SUCCESS] = ServerMessageType.JOIN_SUCCESS
    expected_version: str

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class DropWagonSuccessMessage(BaseModel):
    """Message indicating successful wagon drop."""
    type: Literal[ServerMessageType.DROP_WAGON_SUCCESS] = ServerMessageType.DROP_WAGON_SUCCESS
    cooldown: float

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class DropWagonFailedMessage(BaseModel):
    """Message indicating wagon drop failure."""
    type: Literal[ServerMessageType.DROP_WAGON_FAILED] = ServerMessageType.DROP_WAGON_FAILED
    message: str

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class LeaderboardMessage(BaseModel):
    """Message with leaderboard data."""
    type: Literal[ServerMessageType.LEADERBOARD] = ServerMessageType.LEADERBOARD
    data: list[dict[str, Any]]

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class GameStatusMessage(BaseModel):
    """Message with game status."""
    type: Literal[ServerMessageType.GAME_STATUS] = ServerMessageType.GAME_STATUS
    game_started: bool

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class BestScoreMessage(BaseModel):
    """Message with best score information."""
    type: Literal[ServerMessageType.BEST_SCORE] = ServerMessageType.BEST_SCORE
    best_score: int

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class ErrorMessage(BaseModel):
    """Error message from server."""
    type: Literal[ServerMessageType.ERROR] = ServerMessageType.ERROR
    message: str

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


# =============================================================================
# Client -> Server Messages
# =============================================================================

class AgentIdsMessage(BaseModel):
    """Message with agent identification."""
    type: Literal[ClientMessageType.AGENT_IDS] = ClientMessageType.AGENT_IDS
    nickname: str
    agent_sciper: str
    game_mode: str

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class DirectionActionMessage(BaseModel):
    """Message to change train direction."""
    action: Literal[ClientActionType.DIRECTION] = ClientActionType.DIRECTION
    direction: tuple[int, int]

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class RespawnActionMessage(BaseModel):
    """Message to request respawn."""
    action: Literal[ClientActionType.RESPAWN] = ClientActionType.RESPAWN

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class DropWagonActionMessage(BaseModel):
    """Message to drop a wagon."""
    action: Literal[ClientActionType.DROP_WAGON] = ClientActionType.DROP_WAGON

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class CheckNameActionMessage(BaseModel):
    """Message to check name availability."""
    action: Literal[ClientActionType.CHECK_NAME] = ClientActionType.CHECK_NAME
    nickname: str

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


class CheckSciperActionMessage(BaseModel):
    """Message to check sciper availability."""
    action: Literal[ClientActionType.CHECK_SCIPER] = ClientActionType.CHECK_SCIPER
    agent_sciper: str

    def to_json(self) -> str:
        return self.model_dump_json() + "\n"


# =============================================================================
# Message parsing utilities
# =============================================================================

def parse_server_message(data: dict[str, Any]) -> BaseModel:
    """
    Parse a dictionary into the appropriate server message model.
    
    Args:
        data: Dictionary containing the message data.
        
    Returns:
        The appropriate Pydantic model instance.
        
    Raises:
        ValueError: If the message type is unknown.
    """
    msg_type = data.get("type")
    
    if msg_type == ServerMessageType.STATE:
        return StateMessage(**data)
    elif msg_type == ServerMessageType.GAME_STARTED_SUCCESS:
        return GameStartedSuccessMessage(**data)
    elif msg_type == ServerMessageType.SPAWN_SUCCESS:
        return SpawnSuccessMessage(**data)
    elif msg_type == ServerMessageType.RESPAWN_FAILED:
        return RespawnFailedMessage(**data)
    elif msg_type == ServerMessageType.DEATH:
        return DeathMessage(**data)
    elif msg_type == ServerMessageType.GAME_OVER:
        return GameOverMessage(**data)
    elif msg_type == ServerMessageType.WAITING_ROOM:
        return WaitingRoomMessage(**data)
    elif msg_type == ServerMessageType.INITIAL_STATE:
        return InitialStateMessage(**data)
    elif msg_type == ServerMessageType.PING:
        return PingMessage(**data)
    elif msg_type == ServerMessageType.PONG:
        return PongMessage(**data)
    elif msg_type == ServerMessageType.DISCONNECT:
        return DisconnectMessage(**data)
    elif msg_type == ServerMessageType.NAME_CHECK:
        return NameCheckMessage(**data)
    elif msg_type == ServerMessageType.SCIPER_CHECK:
        return SciperCheckMessage(**data)
    elif msg_type == ServerMessageType.JOIN_SUCCESS:
        return JoinSuccessMessage(**data)
    elif msg_type == ServerMessageType.DROP_WAGON_SUCCESS:
        return DropWagonSuccessMessage(**data)
    elif msg_type == ServerMessageType.DROP_WAGON_FAILED:
        return DropWagonFailedMessage(**data)
    elif msg_type == ServerMessageType.LEADERBOARD:
        return LeaderboardMessage(**data)
    elif msg_type == ServerMessageType.GAME_STATUS:
        return GameStatusMessage(**data)
    elif msg_type == ServerMessageType.BEST_SCORE:
        return BestScoreMessage(**data)
    elif msg_type == ServerMessageType.ERROR:
        return ErrorMessage(**data)
    else:
        raise ValueError(f"Unknown server message type: {msg_type}")


def parse_client_message(data: dict[str, Any]) -> BaseModel:
    """
    Parse a dictionary into the appropriate client message model.
    
    Args:
        data: Dictionary containing the message data.
        
    Returns:
        The appropriate Pydantic model instance.
        
    Raises:
        ValueError: If the message type/action is unknown.
    """
    # Check for type-based messages first
    msg_type = data.get("type")
    if msg_type:
        if msg_type == ClientMessageType.AGENT_IDS:
            return AgentIdsMessage(**data)
        elif msg_type == ClientMessageType.PING:
            return PingMessage(**data)
        elif msg_type == ClientMessageType.PONG:
            return PongMessage(**data)
    
    # Check for action-based messages
    action = data.get("action")
    if action:
        if action == ClientActionType.DIRECTION or action == "direction":
            return DirectionActionMessage(**data)
        elif action == ClientActionType.RESPAWN or action == "respawn":
            return RespawnActionMessage(**data)
        elif action == ClientActionType.DROP_WAGON or action == "drop_wagon":
            return DropWagonActionMessage(**data)
        elif action == ClientActionType.CHECK_NAME or action == "check_name":
            return CheckNameActionMessage(**data)
        elif action == ClientActionType.CHECK_SCIPER or action == "check_sciper":
            return CheckSciperActionMessage(**data)
    
    raise ValueError(f"Unknown client message: {data}")
