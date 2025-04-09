import pytest
import sys
import os
import socket
import threading
from unittest.mock import MagicMock

# Add the parent directory to the Python path to import project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import necessary modules for fixtures
from common.client_config import GameMode

@pytest.fixture
def mock_config():
    """Fixture furnishing a mock configuration for tests"""
    config = MagicMock()
    config.client.host = "localhost"
    config.client.port = 5555
    config.client.game_mode = GameMode.MANUAL
    config.client.manual.nickname = "TestPlayer"
    config.client.screen_width = 800
    config.client.screen_height = 600
    config.client.leaderboard_width = 200
    config.client.server_timeout_seconds = 10
    return config

@pytest.fixture
def mock_socket():
    """Fixture furnishing a mock socket for tests"""
    mock_sock = MagicMock(spec=socket.socket)
    mock_sock.recvfrom.return_value = (b'{"type": "ping"}', ('127.0.0.1', 5555))
    mock_sock.getsockname.return_value = ('127.0.0.1', 12345)
    return mock_sock

@pytest.fixture
def mock_client():
    """Fixture furnishing a mock client for tests"""
    client = MagicMock()
    client.config.game_mode = GameMode.MANUAL
    client.config.server_timeout_seconds = 10
    client.trains = {}
    client.passengers = []
    client.delivery_zone = {}
    client.is_dead = False
    client.waiting_for_respawn = False
    client.running = True
    client.lock = threading.Lock()
    return client

@pytest.fixture
def mock_server():
    """Fixture furnishing a mock server for tests"""
    server = MagicMock()
    server.config.host = "localhost"
    server.config.port = 5555
    server.config.nb_clients_per_room = 4
    server.rooms = {}
    server.running = True
    server.addr_to_name = {}
    server.addr_to_sciper = {}
    server.addr_to_game_mode = {}
    server.sciper_to_addr = {}
    server.client_last_activity = {}
    server.disconnected_clients = set()
    return server
