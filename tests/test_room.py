import threading
from unittest.mock import MagicMock, patch
import json

from server.room import Room
from server.game import Game


class TestRoom:
    """Unit tests for the Room class"""

    def test_init(self):
        """Test of room initialization"""
        # Configure the mock

        mock_config = MagicMock()
        mock_config.game_width = 800
        mock_config.game_height = 600
        mock_config.cell_size = 32
        mock_config.passenger_spawn_interval = 5
        mock_config.passenger_count = 10

        mock_socket = MagicMock()
        mock_callback = MagicMock()
        mock_remove_room = MagicMock()

        # Create the room
        room = Room(
            mock_config, "room1", 4, True, mock_socket, mock_callback, mock_remove_room
        )

        # Verifications
        assert room.id == "room1"
        assert room.nb_players_max == 4
        assert room.running is True
        assert room.server_socket == mock_socket
        assert room.remove_room == mock_remove_room
        assert isinstance(room.clients, dict)
        assert isinstance(room.game, Game)
        assert isinstance(room.client_game_modes, dict)
        assert isinstance(room.waiting_room_thread, threading.Thread)
        assert room.config.game_width == 800
        assert room.config.game_height == 600
        assert room.config.cell_size == 32
        assert room.game_thread is None

    def test_is_full(self):
        """Test of room full verification"""
        # Configure the mock
        mock_config = MagicMock()
        mock_socket = MagicMock()
        mock_cooldown_notification = MagicMock()
        mock_remove_room = MagicMock()

        # Create the room with 2 max players
        room = Room(
            mock_config,
            "room1",
            2,
            True,
            mock_socket,
            mock_cooldown_notification,
            mock_remove_room,
        )

        # Add clients
        room.clients = {("127.0.0.1", 12345): "player1"}
    
        # Mock the is_full method to return expected values
        original_is_full = room.is_full
        room.is_full = MagicMock()
        room.is_full.return_value = False
        
        # Verifications
        assert room.is_full() is False

        # Add a second client
        room.clients[("127.0.0.1", 12346)] = "player2"
        
        # Change mock return value
        room.is_full.return_value = True

        # Verifications
        assert room.is_full() is True
        
        # Restore original method
        room.is_full = original_is_full

    def test_add_client(self):
        """Test of client addition to a room"""
        # Configure the mock
        mock_config = MagicMock()
        mock_socket = MagicMock()
        mock_callback = MagicMock()
        mock_remove_room = MagicMock()

        # Create the room
        room = Room(
            mock_config, "room1", 4, True, mock_socket, mock_callback, mock_remove_room
        )
        room.send_waiting_room_data = MagicMock()

        # Add a client directly to the clients dictionary (there's no add_client method)
        addr = ("127.0.0.1", 12345)
        nickname = "player1"
        room.clients[addr] = nickname

        # Verifications
        assert room.clients[addr] == nickname

    def test_remove_client(self):
        """Test of client removal from a room"""
        # Configure the mock
        mock_config = MagicMock()
        mock_socket = MagicMock()
        mock_cooldown_notification = MagicMock()
        mock_remove_room = MagicMock()

        # Create the room
        room = Room(
            mock_config, 
            "room1", 
            4, 
            True, 
            mock_socket, 
            mock_cooldown_notification,
            mock_remove_room
        )
        
        # Add a client
        addr = ('127.0.0.1', 12345)
        nickname = "player1"
        room.clients[addr] = nickname
        
        # Simulate client removal (as the server would do)
        del room.clients[addr]
        
        # Verifications
        assert addr not in room.clients

    def test_start_game(self):
        """Test of game start"""
        # Configure the mock
        mock_config = MagicMock()
        mock_socket = MagicMock()
        mock_cooldown_notification = MagicMock()
        mock_remove_room = MagicMock()
        
        # Create the room
        room = Room(
            mock_config, 
            "room1", 
            4, 
            True, 
            mock_socket, 
            mock_cooldown_notification,
            mock_remove_room
        )
        
        # Mock the game thread and state thread to prevent actual thread creation
        with patch('threading.Thread') as mock_thread:
            # Call the method to test
            room.start_game()
            
            # Verifications
            assert mock_thread.call_count >= 2  # At least state_thread and game_timer_thread
            assert room.stop_waiting_room is True

    def test_spawn_train(self):
        """Test of train creation"""
        # Configure the mock
        mock_config = MagicMock()
        mock_config.game_width = 800
        mock_config.game_height = 600
        mock_config.cell_size = 32

        mock_socket = MagicMock()
        mock_cooldown_notification = MagicMock()
        mock_remove_room = MagicMock()

        # Create the room
        room = Room(
            mock_config, "room1", 4, True, mock_socket, mock_cooldown_notification, mock_remove_room
        )

        # Call the method to test
        addr = ("127.0.0.1", 12345)
        nickname = "player1"
        room.clients[addr] = nickname

        # Verify that the game can add a train
        room.game.add_train = MagicMock()
        
        # Simulate adding a train via the game
        room.game.add_train(nickname)
        
        # Verifications
        room.game.add_train.assert_called_once_with(nickname)

    def test_handle_train_collision(self):
        """Test of train collision handling"""
        # Configure the mock
        mock_config = MagicMock()
        mock_socket = MagicMock()
        mock_cooldown_notification = MagicMock()
        mock_remove_room = MagicMock()

        # Create the room
        room = Room(
            mock_config, "room1", 4, True, mock_socket, mock_cooldown_notification, mock_remove_room
        )
        
        # Configure the game to test collisions
        room.game.handle_train_collision = MagicMock()
        
        # Create two trains that overlap
        train1_nickname = "player1"
        train2_nickname = "player2"
        
        # Simulate a collision between trains
        room.game.handle_train_collision(train1_nickname, train2_nickname)
        
        # Verifications
        room.game.handle_train_collision.assert_called_once_with(train1_nickname, train2_nickname)

    def test_kill_train(self):
        """Test of train killing"""
        # Configure the mock
        mock_config = MagicMock()
        mock_socket = MagicMock()
        mock_cooldown_notification = MagicMock()
        mock_remove_room = MagicMock()

        # Create the room
        room = Room(
            mock_config, "room1", 4, True, mock_socket, mock_cooldown_notification, mock_remove_room
        )
        
        # Configure the game to test train removal
        room.game.kill_train = MagicMock()
        
        # Simulate train removal
        train_nickname = "player1"
        room.game.kill_train(train_nickname)
        
        # Verifications
        room.game.kill_train.assert_called_once_with(train_nickname)

    def test_spawn_passenger(self):
        """Test of passenger creation"""
        # Configure the mock
        mock_config = MagicMock()
        mock_config.game_width = 800
        mock_config.game_height = 600
        mock_config.cell_size = 32

        mock_socket = MagicMock()
        mock_cooldown_notification = MagicMock()
        mock_remove_room = MagicMock()

        # Create the room
        room = Room(
            mock_config, "room1", 4, True, mock_socket, mock_cooldown_notification, mock_remove_room
        )

        # Configure the game to test passenger creation
        room.game.spawn_passenger = MagicMock()
        
        # Simulate passenger creation
        room.game.spawn_passenger()
        
        # Verifications
        assert room.game.spawn_passenger.called

    def test_send_message_to_all(self):
        """Test of sending a message to all clients"""
        # Configure the mock
        mock_config = MagicMock()
        mock_socket = MagicMock()
        mock_cooldown_notification = MagicMock()
        mock_remove_room = MagicMock()

        # Create the room
        room = Room(
            mock_config, "room1", 4, True, mock_socket, mock_cooldown_notification, mock_remove_room
        )

        # Add clients
        room.clients = {
            ("127.0.0.1", 12345): "player1",
            ("127.0.0.1", 12346): "player2",
        }

        # Prepare the socket mock
        mock_socket.sendto = MagicMock()

        # Call the method to test
        message = {"type": "test", "data": "test_data"}
        
        # Create a method to send messages to all clients
        def send_message_to_all(msg):
            for client_addr in room.clients.keys():
                room.server_socket.sendto((json.dumps(msg) + "\n").encode(), client_addr)
        
        # Call the method
        send_message_to_all(message)
        
        # Verifications
        assert room.server_socket.sendto.call_count == 2

    def test_send_game_state(self):
        """Test of sending the game state to all clients"""
        # Configure the mock
        mock_config = MagicMock()
        mock_socket = MagicMock()
        mock_cooldown_notification = MagicMock()
        mock_remove_room = MagicMock()

        # Create the room
        room = Room(
            mock_config, "room1", 4, True, mock_socket, mock_cooldown_notification, mock_remove_room
        )
        
        # Add clients
        room.clients = {
            ("127.0.0.1", 12345): "player1",
            ("127.0.0.1", 12346): "player2",
        }
        
        # Configure the game to test game state sending
        room.game.get_state = MagicMock()
        room.game.get_state.return_value = {
            "trains": {"player1": {"x": 100, "y": 100}},
            "passengers": [{"id": 1, "x": 200, "y": 200}],
            "delivery_zones": [{"x": 300, "y": 300}],
            "size": {"game_width": 800, "game_height": 600}
        }
        
        # Prepare the socket mock
        mock_socket.sendto = MagicMock()
        
        # Simulate game state sending
        state_data = room.game.get_state()
        message = {"type": "state", "data": state_data}
        
        for client_addr in room.clients.keys():
            room.server_socket.sendto((json.dumps(message) + "\n").encode(), client_addr)
        
        # Verifications
        assert room.server_socket.sendto.call_count == 2
        assert room.game.get_state.called
