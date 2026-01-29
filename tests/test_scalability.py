"""
Scalability performance tests for I Like Trains.
Tests server performance with varying numbers of players and rooms.

Test scenarios:
1. Single room with 5, 10, 20, 50, 100 simultaneous players
2. Multiple rooms: 20 rooms with 4 players each (80 total players)
"""

import time
import statistics
import logging
import threading
import socket
import json
import sys
import os
import random
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_scalability")


class ScalabilityResult:
    """Container for scalability test results"""
    def __init__(self, name: str, player_count: int, room_count: int, metrics: dict):
        self.name = name
        self.player_count = player_count
        self.room_count = room_count
        self.metrics = metrics
        
    def __str__(self):
        lines = [
            f"\n{'='*70}",
            f"  {self.name}",
            f"{'='*70}",
            f"  Players: {self.player_count} | Rooms: {self.room_count}",
        ]
        for key, value in self.metrics.items():
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.4f}")
            else:
                lines.append(f"  {key}: {value}")
        lines.append("="*70)
        return "\n".join(lines)


class ScalabilityTestClient:
    """Lightweight test client for scalability measurements"""
    
    def __init__(self, host: str, port: int, nickname: str, sciper: str):
        self.host = host
        self.port = port
        self.nickname = nickname
        self.sciper = sciper
        self.socket = None
        self.server_addr = (host, port)
        self.running = False
        self.receive_thread = None
        self.connected = False
        self.game_started = False
        self.messages_received = 0
        self.state_updates_received = 0
        self.last_state_time = 0
        self.state_intervals = []
        self.connection_time = 0
        self.errors = []
        
    def connect(self, timeout: float = 10.0) -> bool:
        """Connect to server and send agent IDs"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(("0.0.0.0", 0))
            self.socket.settimeout(timeout)
            self.running = True
            
            # Start receive thread
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
            # Send agent IDs
            start_time = time.perf_counter()
            agent_ids_msg = {
                "type": "agent_ids",
                "nickname": self.nickname,
                "agent_sciper": self.sciper,
                "game_mode": "agent"
            }
            self._send_message(agent_ids_msg)
            
            # Wait for connection confirmation
            start = time.time()
            while not self.connected and time.time() - start < timeout:
                time.sleep(0.05)
            
            if self.connected:
                self.connection_time = time.perf_counter() - start_time
            
            return self.connected
            
        except Exception as e:
            self.errors.append(f"Connection error: {e}")
            logger.error(f"Client {self.nickname} connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from server"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None
    
    def _send_message(self, message: dict) -> bool:
        """Send message to server"""
        if not self.socket:
            return False
        try:
            data = json.dumps(message) + "\n"
            self.socket.sendto(data.encode(), self.server_addr)
            return True
        except Exception as e:
            self.errors.append(f"Send error: {e}")
            return False
    
    def send_direction(self, direction: list):
        """Send direction command"""
        self._send_message({"action": "direction", "direction": direction})
    
    def _receive_loop(self):
        """Receive messages from server"""
        while self.running:
            try:
                self.socket.settimeout(0.1)
                data, addr = self.socket.recvfrom(65536)
                
                if not data:
                    continue
                
                receive_time = time.perf_counter()
                messages = data.decode().split("\n")
                
                for msg in messages:
                    if not msg:
                        continue
                    
                    try:
                        message = json.loads(msg)
                        msg_type = message.get("type")
                        self.messages_received += 1
                        
                        if msg_type == "name_check":
                            if not message.get("available", True):
                                self.errors.append(f"Name not available: {message.get('reason')}")
                        
                        elif msg_type == "join_success" or msg_type == "waiting_room":
                            self.connected = True
                        
                        elif msg_type == "game_started_success":
                            self.game_started = True
                        
                        elif msg_type == "state":
                            self.state_updates_received += 1
                            if self.last_state_time > 0:
                                interval = receive_time - self.last_state_time
                                self.state_intervals.append(interval)
                            self.last_state_time = receive_time
                        
                        elif msg_type == "ping":
                            self._send_message({"type": "pong"})
                        
                        elif msg_type == "disconnect":
                            self.errors.append(f"Disconnected: {message.get('reason')}")
                            self.running = False
                        
                    except json.JSONDecodeError:
                        pass
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.errors.append(f"Receive error: {e}")


class ScalabilityServerManager:
    """Manages a server instance for scalability testing"""
    
    def __init__(self, port: int, nb_players_per_room: int, use_multiprocessing: bool = True):
        self.port = port
        self.nb_players_per_room = nb_players_per_room
        self.use_multiprocessing = use_multiprocessing
        self.server = None
        self.server_thread = None
        self.running = False
    
    def start(self) -> bool:
        """Start the server in a background thread"""
        try:
            from server.server import Server
            from common.config import Config
            
            config_dict = {
                "server": {
                    "host": "127.0.0.1",
                    "port": self.port,
                    "nb_players_per_room": self.nb_players_per_room,
                    "waiting_time_before_bots_seconds": 60,  # Long wait to allow all clients to connect
                    "game_duration_seconds": 30,
                    "grading_mode": False,
                    "use_multiprocessing": self.use_multiprocessing,
                    "agents": []  # No bots for scalability tests
                },
                "client": {
                    "host": "127.0.0.1",
                    "port": self.port,
                    "game_mode": "agent",
                    "sciper": "000000",
                    "agent": {"nickname": "Test", "agent_file_name": "agent.py"},
                    "manual": {"nickname": "Test"}
                }
            }
            
            config = Config(**config_dict)
            
            self.running = True
            
            def run_server():
                try:
                    self.server = Server(config)
                except Exception as e:
                    logger.error(f"Server error: {e}")
                    self.running = False
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            # Wait for server to start
            time.sleep(1.5)
            return self.running
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False
    
    def stop(self):
        """Stop the server"""
        self.running = False
        if self.server:
            self.server.running = False
            if hasattr(self.server, 'room_process_manager') and self.server.room_process_manager:
                try:
                    self.server.room_process_manager.shutdown()
                except Exception:
                    pass
            if hasattr(self.server, 'server_socket'):
                try:
                    self.server.server_socket.close()
                except Exception:
                    pass


class ScalabilityTests:
    """Scalability test suite"""
    
    def __init__(self, base_port: int = 16000, test_duration: float = 15.0):
        self.base_port = base_port
        self.current_port = base_port
        self.test_duration = test_duration
        self.results = []
        self.server_manager = None
    
    def _get_next_port(self) -> int:
        """Get next available port"""
        self.current_port += 1
        return self.current_port
    
    def _start_server(self, nb_players_per_room: int, use_multiprocessing: bool = True) -> bool:
        """Start a fresh server instance"""
        if self.server_manager:
            self.server_manager.stop()
            time.sleep(1.0)
        
        port = self._get_next_port()
        self.server_manager = ScalabilityServerManager(
            port=port,
            nb_players_per_room=nb_players_per_room,
            use_multiprocessing=use_multiprocessing
        )
        return self.server_manager.start()
    
    def _connect_clients(self, count: int, batch_id: int) -> list:
        """Connect multiple clients to the server"""
        clients = []
        threads = []
        
        def connect_client(client):
            client.connect(timeout=15.0)
        
        # Create all clients
        for i in range(count):
            nickname = f"Scale_{batch_id}_{i}"
            # Sciper must be exactly 6 digits
            sciper = f"{100000 + (batch_id % 900) * 100 + (i % 100):06d}"
            client = ScalabilityTestClient(
                "127.0.0.1", 
                self.server_manager.port, 
                nickname, 
                sciper
            )
            clients.append(client)
        
        # Connect all clients in parallel
        for client in clients:
            t = threading.Thread(target=connect_client, args=(client,))
            threads.append(t)
            t.start()
            time.sleep(0.05)  # Small delay between connection attempts
        
        # Wait for all connections
        for t in threads:
            t.join(timeout=20.0)
        
        return clients
    
    def _collect_metrics(self, clients: list, duration: float) -> dict:
        """Collect performance metrics from clients during test duration"""
        # Let the game run and collect data
        start_time = time.time()
        
        # Simulate player activity
        directions = [[1, 0], [0, 1], [-1, 0], [0, -1]]
        while time.time() - start_time < duration:
            for client in clients:
                if client.connected:
                    client.send_direction(random.choice(directions))
            time.sleep(0.1)
        
        # Collect metrics
        connected_count = sum(1 for c in clients if c.connected)
        game_started_count = sum(1 for c in clients if c.game_started)
        total_state_updates = sum(c.state_updates_received for c in clients)
        total_messages = sum(c.messages_received for c in clients)
        
        # Calculate state update frequency
        all_intervals = []
        for c in clients:
            all_intervals.extend(c.state_intervals)
        
        avg_state_interval = statistics.mean(all_intervals) if all_intervals else 0
        state_hz = 1.0 / avg_state_interval if avg_state_interval > 0 else 0
        
        # Connection times
        connection_times = [c.connection_time for c in clients if c.connection_time > 0]
        avg_connection_time = statistics.mean(connection_times) if connection_times else 0
        
        # Errors
        all_errors = []
        for c in clients:
            all_errors.extend(c.errors)
        
        return {
            "connected_count": connected_count,
            "game_started_count": game_started_count,
            "total_state_updates": total_state_updates,
            "total_messages": total_messages,
            "avg_state_interval_ms": avg_state_interval * 1000,
            "state_update_hz": state_hz,
            "avg_connection_time_ms": avg_connection_time * 1000,
            "error_count": len(all_errors),
            "errors": all_errors[:10] if all_errors else []  # First 10 errors
        }
    
    def test_single_room_scalability(self, player_counts: list = None):
        """Test single room with varying player counts"""
        if player_counts is None:
            player_counts = [5, 10, 20, 50, 100]
        
        print("\n" + "="*70)
        print("  SINGLE ROOM SCALABILITY TEST")
        print("="*70)
        
        for count in player_counts:
            print(f"\n  Testing {count} players in single room...")
            
            # Start server with room size matching player count
            if not self._start_server(nb_players_per_room=count, use_multiprocessing=True):
                print(f"    ERROR: Failed to start server for {count} players")
                continue
            
            print(f"    Server started on port {self.server_manager.port}")
            
            batch_id = random.randint(1000, 9999)
            clients = self._connect_clients(count, batch_id)
            
            connected = sum(1 for c in clients if c.connected)
            print(f"    Connected: {connected}/{count} clients")
            
            if connected == 0:
                print("    ERROR: No clients connected")
                for c in clients:
                    c.disconnect()
                self.server_manager.stop()
                continue
            
            # Wait a bit for game to start
            time.sleep(3.0)
            
            # Collect metrics
            print(f"    Running test for {self.test_duration}s...")
            metrics = self._collect_metrics(clients, self.test_duration)
            
            result = ScalabilityResult(
                name=f"Single Room - {count} Players",
                player_count=count,
                room_count=1,
                metrics=metrics
            )
            self.results.append(result)
            
            print(f"    State updates: {metrics['total_state_updates']} ({metrics['state_update_hz']:.1f} Hz)")
            print(f"    Avg connection time: {metrics['avg_connection_time_ms']:.2f} ms")
            if metrics['error_count'] > 0:
                print(f"    Errors: {metrics['error_count']}")
            
            # Cleanup
            for c in clients:
                c.disconnect()
            self.server_manager.stop()
            time.sleep(1.0)
    
    def test_multiple_rooms(self, room_count: int = 20, players_per_room: int = 4):
        """Test multiple rooms with fixed players per room"""
        total_players = room_count * players_per_room
        
        print("\n" + "="*70)
        print("  MULTIPLE ROOMS SCALABILITY TEST")
        print("  {} rooms x {} players = {} total".format(room_count, players_per_room, total_players))
        print("="*70)
        
        # Start server
        if not self._start_server(nb_players_per_room=players_per_room, use_multiprocessing=True):
            print("    ERROR: Failed to start server")
            return
        
        print(f"    Server started on port {self.server_manager.port}")
        
        all_clients = []
        
        # Connect clients in batches (one room at a time)
        for room_idx in range(room_count):
            batch_id = random.randint(10000, 99999)
            print(f"    Connecting room {room_idx + 1}/{room_count}...")
            
            clients = self._connect_clients(players_per_room, batch_id)
            all_clients.extend(clients)
            
            connected = sum(1 for c in clients if c.connected)
            if connected < players_per_room:
                print(f"      Warning: Only {connected}/{players_per_room} connected")
            
            # Small delay between rooms
            time.sleep(0.5)
        
        total_connected = sum(1 for c in all_clients if c.connected)
        print(f"\n    Total connected: {total_connected}/{total_players}")
        
        # Wait for games to start
        time.sleep(5.0)
        
        # Collect metrics
        print(f"    Running test for {self.test_duration}s...")
        metrics = self._collect_metrics(all_clients, self.test_duration)
        
        result = ScalabilityResult(
            name=f"Multiple Rooms - {room_count}x{players_per_room}",
            player_count=total_players,
            room_count=room_count,
            metrics=metrics
        )
        self.results.append(result)
        
        print("\n    Results:")
        print(f"      Connected: {metrics['connected_count']}/{total_players}")
        print(f"      State updates: {metrics['total_state_updates']} ({metrics['state_update_hz']:.1f} Hz)")
        print(f"      Avg connection time: {metrics['avg_connection_time_ms']:.2f} ms")
        if metrics['error_count'] > 0:
            print(f"      Errors: {metrics['error_count']}")
        
        # Cleanup
        for c in all_clients:
            c.disconnect()
        self.server_manager.stop()
    
    def run_all_tests(self):
        """Run all scalability tests"""
        print("\n" + "="*70)
        print("  I LIKE TRAINS - SCALABILITY TESTS")
        print("="*70)
        print(f"  Test duration: {self.test_duration}s per scenario")
        print("="*70)
        
        # Test 1: Single room with varying player counts
        self.test_single_room_scalability([5, 10, 20, 50, 100])
        
        # Test 2: Multiple rooms
        self.test_multiple_rooms(room_count=20, players_per_room=4)
        
        self._print_summary()
        return self.results
    
    def _print_summary(self):
        """Print summary of all test results"""
        print("\n" + "="*70)
        print("  SCALABILITY TEST SUMMARY")
        print("="*70)
        
        print("\n  {:35} | {:8} | {:6} | {:10} | {:10}".format('Test Name', 'Players', 'Rooms', 'Connected', 'State Hz'))
        print("  " + "-"*85)
        
        for result in self.results:
            connected = result.metrics.get('connected_count', 0)
            state_hz = result.metrics.get('state_update_hz', 0)
            print(f"  {result.name:<35} | {result.player_count:<8} | {result.room_count:<6} | {connected:<10} | {state_hz:<10.1f}")
        
        print("\n" + "="*70 + "\n")


def run_scalability_tests(base_port: int = 16000, duration: float = 15.0, 
                          player_counts: list = None, room_count: int = 20, 
                          players_per_room: int = 4):
    """Run scalability tests with custom parameters"""
    tests = ScalabilityTests(base_port=base_port, test_duration=duration)
    
    if player_counts:
        tests.test_single_room_scalability(player_counts)
    
    if room_count > 0:
        tests.test_multiple_rooms(room_count=room_count, players_per_room=players_per_room)
    
    tests._print_summary()
    return tests.results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run scalability tests for I Like Trains",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tests.test_scalability                           # Run all tests
  python -m tests.test_scalability --players 5 10 20         # Test specific player counts
  python -m tests.test_scalability --rooms 20 --per-room 4   # Test 20 rooms with 4 players each
  python -m tests.test_scalability --duration 30             # Run tests for 30 seconds each
        """
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=16000,
        help="Base port for test servers (default: 16000)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=15.0,
        help="Duration for each test scenario in seconds (default: 15.0)"
    )
    parser.add_argument(
        "--players",
        type=int,
        nargs="+",
        default=None,
        help="Player counts to test in single room (default: 5 10 20 50 100)"
    )
    parser.add_argument(
        "--rooms",
        type=int,
        default=20,
        help="Number of rooms for multi-room test (default: 20, 0 to skip)"
    )
    parser.add_argument(
        "--per-room",
        type=int,
        default=4,
        help="Players per room for multi-room test (default: 4)"
    )
    parser.add_argument(
        "--single-room-only",
        action="store_true",
        help="Only run single room tests"
    )
    parser.add_argument(
        "--multi-room-only",
        action="store_true",
        help="Only run multi-room tests"
    )
    
    args = parser.parse_args()
    
    print("\nRunning scalability tests...\n")
    
    tests = ScalabilityTests(base_port=args.port, test_duration=args.duration)
    
    if args.multi_room_only:
        tests.test_multiple_rooms(room_count=args.rooms, players_per_room=args.per_room)
    elif args.single_room_only:
        player_counts = args.players if args.players else [5, 10, 20, 50, 100]
        tests.test_single_room_scalability(player_counts)
    else:
        player_counts = args.players if args.players else [5, 10, 20, 50, 100]
        tests.test_single_room_scalability(player_counts)
        if args.rooms > 0:
            tests.test_multiple_rooms(room_count=args.rooms, players_per_room=args.per_room)
    
    tests._print_summary()
