"""
Live integration performance test for I Like Trains.
Starts a server, connects multiple clients, and measures connection/communication performance.
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

from common.server_config import ServerConfig
from common.constants import REFERENCE_TICK_RATE

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_live_performance")


class PerformanceResult:
    """Container for performance test results"""
    def __init__(self, name: str, times: list[float]):
        self.name = name
        self.times = times
        self.mean = statistics.mean(times) if times else 0
        self.median = statistics.median(times) if times else 0
        self.stdev = statistics.stdev(times) if len(times) > 1 else 0
        self.min_time = min(times) if times else 0
        self.max_time = max(times) if times else 0
        self.iterations = len(times)

    def __str__(self):
        return (
            f"\n{'='*60}\n"
            f"  {self.name}\n"
            f"{'='*60}\n"
            f"  Samples:    {self.iterations}\n"
            f"  Mean:       {self.mean*1000:.4f} ms\n"
            f"  Median:     {self.median*1000:.4f} ms\n"
            f"  Std Dev:    {self.stdev*1000:.4f} ms\n"
            f"  Min:        {self.min_time*1000:.4f} ms\n"
            f"  Max:        {self.max_time*1000:.4f} ms\n"
        )


class TestClient:
    """Lightweight test client for performance measurements"""
    
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
        self.messages_received = 0
        self.state_updates_received = 0
        self.last_state_time = 0
        self.state_intervals = []
        self.ping_times = []
        self.pending_pings = {}  # ping_id -> send_time
        
    def connect(self, timeout: float = 5.0) -> bool:
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
            
            return self.connected
            
        except Exception as e:
            logger.error(f"Client {self.nickname} connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from server"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
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
            logger.error(f"Send error: {e}")
            return False
    
    def send_ping(self) -> float:
        """Send ping and return send time"""
        ping_id = str(random.randint(100000, 999999))
        send_time = time.perf_counter()
        self.pending_pings[ping_id] = send_time
        self._send_message({"type": "ping", "id": ping_id})
        return send_time
    
    def send_move(self, direction: list):
        """Send move command"""
        self._send_message({"action": "change_direction", "direction": direction})
    
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
                        
                        if msg_type == "join_success":
                            self.connected = True
                            logger.debug(f"Client {self.nickname} connected")
                        
                        elif msg_type == "state":
                            self.state_updates_received += 1
                            if self.last_state_time > 0:
                                interval = receive_time - self.last_state_time
                                self.state_intervals.append(interval)
                            self.last_state_time = receive_time
                        
                        elif msg_type == "ping":
                            # Respond to server ping
                            self._send_message({"type": "pong"})
                        
                        elif msg_type == "pong":
                            # Calculate round-trip time
                            for ping_id, send_time in list(self.pending_pings.items()):
                                rtt = receive_time - send_time
                                self.ping_times.append(rtt)
                                del self.pending_pings[ping_id]
                                break
                        
                    except json.JSONDecodeError:
                        pass
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.debug(f"Receive error: {e}")


class LiveServerManager:
    """Manages a live server instance for testing"""
    
    def __init__(self, port: int = 15555):
        self.port = port
        self.server = None
        self.server_thread = None
        self.running = False
    
    def start(self) -> bool:
        """Start the server in a background thread"""
        try:
            from server.server import Server
            from common.config import Config
            
            # Create config with test settings
            # Check if USE_MULTIPROCESSING env var is set for testing
            use_mp = os.environ.get('USE_MULTIPROCESSING', 'false').lower() == 'true'
            
            config_dict = {
                "server": {
                    "host": "127.0.0.1",
                    "port": self.port,
                    "nb_players_per_room": 4,
                    "waiting_time_before_bots_seconds": 2,
                    "game_duration_seconds": 30,
                    "grading_mode": False,
                    "use_multiprocessing": use_mp,
                    "agents": []
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
            
            # Start server in thread
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
            time.sleep(1.0)
            return self.running
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            return False
    
    def stop(self):
        """Stop the server"""
        self.running = False
        if self.server:
            self.server.running = False
            if hasattr(self.server, 'server_socket'):
                try:
                    self.server.server_socket.close()
                except:
                    pass


class LivePerformanceTests:
    """Live integration performance test suite"""
    
    def __init__(self, port: int = 15555, test_duration: float = 10.0):
        self.port = port
        self.test_duration = test_duration
        self.results = []
        self.server_manager = None
    
    def _start_fresh_server(self):
        """Start a fresh server instance"""
        if self.server_manager:
            self.server_manager.stop()
            time.sleep(0.5)
        self.port += 1  # Use different port for each server
        self.server_manager = LiveServerManager(port=self.port)
        return self.server_manager.start()

    def run_all_tests(self):
        """Run all live performance tests"""
        logger.info("Starting live performance tests...")
        
        print("\n" + "="*70)
        print("  LIVE INTEGRATION PERFORMANCE TESTS")
        print("="*70)
        print(f"  Test duration: {self.test_duration}s per test")
        print(f"  Starting port: {self.port}")
        print("="*70 + "\n")
        
        # Run each test with a fresh server to avoid socket issues
        tests = [
            ("Single Client Connection", self.test_single_client_connection),
            ("Ping Latency", self.test_ping_latency),
            ("State Update Frequency", self.test_state_update_frequency),
            ("Message Throughput", self.test_message_throughput),
        ]
        
        for test_name, test_func in tests:
            print(f"  Starting server for: {test_name}...")
            if not self._start_fresh_server():
                print(f"    ERROR: Failed to start server for {test_name}")
                continue
            print(f"    Server ready on port {self.port}")
            
            try:
                test_func()
            except Exception as e:
                print(f"    ERROR in test: {e}")
            finally:
                self.server_manager.stop()
                time.sleep(0.3)
        
        self._print_summary()
        return self.results
    
    def test_single_client_connection(self):
        """Test single client connection time"""
        print("  Running: Single Client Connection Time...")
        
        times = []
        for i in range(5):
            client = TestClient("127.0.0.1", self.port, f"ConnTest_{i}_{random.randint(1000,9999)}", f"{100000+i}")
            
            start = time.perf_counter()
            success = client.connect(timeout=3.0)
            end = time.perf_counter()
            
            if success:
                times.append(end - start)
                logger.debug(f"Client {i} connected in {(end-start)*1000:.2f} ms")
            else:
                logger.debug(f"Client {i} failed to connect")
            
            client.disconnect()
            time.sleep(0.3)
        
        if times:
            result = PerformanceResult("Single Client Connection", times)
            self.results.append(result)
            print(f"    Mean connection time: {result.mean*1000:.2f} ms ({len(times)} successful)")
    
    def test_multiple_client_connections(self):
        """Test multiple simultaneous client connections"""
        print("  Running: Multiple Client Connections...")
        
        client_counts = [2]
        batch_id = random.randint(1000, 9999)
        
        for count in client_counts:
            clients = []
            times = []
            
            start = time.perf_counter()
            
            # Connect all clients
            for i in range(count):
                client = TestClient("127.0.0.1", self.port, f"Multi_{batch_id}_{i}", f"{200000+i}")
                if client.connect(timeout=5.0):
                    clients.append(client)
            
            end = time.perf_counter()
            
            connected_count = len(clients)
            if connected_count > 0:
                avg_time = (end - start) / connected_count
                times.append(avg_time)
                
                result = PerformanceResult(f"Connect {count} Clients (avg)", times)
                self.results.append(result)
                print(f"    {connected_count}/{count} connected, avg: {avg_time*1000:.2f} ms")
            
            # Disconnect all
            for client in clients:
                client.disconnect()
            
            time.sleep(1.0)
    
    def test_ping_latency(self):
        """Test ping/pong round-trip latency"""
        print("  Running: Ping Latency Test...")
        
        client = TestClient("127.0.0.1", self.port, f"Ping_{random.randint(1000,9999)}", "300000")
        if not client.connect(timeout=5.0):
            print("    ERROR: Failed to connect client")
            return
        
        # Wait for game to potentially start
        time.sleep(2.0)
        
        # Send multiple pings
        for _ in range(50):
            client.send_ping()
            time.sleep(0.1)
        
        # Wait for responses
        time.sleep(1.0)
        
        if client.ping_times:
            result = PerformanceResult("Ping Round-Trip Latency", client.ping_times)
            self.results.append(result)
            print(f"    Mean RTT: {result.mean*1000:.2f} ms ({len(client.ping_times)} samples)")
        else:
            print("    No ping responses received")
        
        client.disconnect()
    
    def test_state_update_frequency(self):
        """Test game state update frequency"""
        print("  Running: State Update Frequency Test...")
        
        client = TestClient("127.0.0.1", self.port, f"State_{random.randint(1000,9999)}", "400000")
        if not client.connect(timeout=5.0):
            print("    ERROR: Failed to connect client")
            return
        
        # Wait for game to start and collect state updates
        print(f"    Collecting state updates for {self.test_duration}s...")
        time.sleep(self.test_duration)
        
        if client.state_intervals:
            result = PerformanceResult("State Update Interval", client.state_intervals)
            self.results.append(result)
            
            avg_interval = result.mean
            estimated_hz = 1.0 / avg_interval if avg_interval > 0 else 0
            
            print(f"    Updates received: {client.state_updates_received}")
            print(f"    Mean interval: {avg_interval*1000:.2f} ms ({estimated_hz:.1f} Hz)")
        else:
            print(f"    State updates received: {client.state_updates_received}")
            print("    Not enough data for interval calculation")
        
        client.disconnect()
    
    def test_message_throughput(self):
        """Test message sending throughput"""
        print("  Running: Message Throughput Test...")
        
        client = TestClient("127.0.0.1", self.port, f"Throughput_{random.randint(1000,9999)}", "500000")
        if not client.connect(timeout=5.0):
            print("    ERROR: Failed to connect client")
            return
        
        # Wait for game
        time.sleep(2.0)
        
        # Send many move commands and measure throughput
        directions = [[1, 0], [0, 1], [-1, 0], [0, -1]]
        msg_count = 1000
        
        start = time.perf_counter()
        for i in range(msg_count):
            client.send_move(directions[i % 4])
        end = time.perf_counter()
        
        duration = end - start
        throughput = msg_count / duration
        
        print(f"    Sent {msg_count} messages in {duration*1000:.2f} ms")
        print(f"    Throughput: {throughput:.0f} msg/sec")
        
        # Store as a result
        self.results.append(PerformanceResult(
            "Message Send Throughput",
            [duration / msg_count] * msg_count  # Individual message times
        ))
        
        client.disconnect()
    
    def _print_summary(self):
        """Print summary of all test results"""
        print("\n" + "="*70)
        print("  LIVE PERFORMANCE TEST SUMMARY")
        print("="*70)
        
        for result in self.results:
            throughput = 1/result.mean if result.mean > 0 else 0
            print(f"  {result.name:40} | {result.mean*1000:8.4f} ms | {throughput:8.0f} ops/sec")
        
        print("="*70 + "\n")


def run_live_performance_tests(port: int = 15555, duration: float = 10.0):
    """Run live performance tests"""
    tests = LivePerformanceTests(port=port, test_duration=duration)
    return tests.run_all_tests()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run live integration performance tests")
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=15555,
        help="Port for test server (default: 15555)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=10.0,
        help="Duration for time-based tests in seconds (default: 10.0)"
    )
    args = parser.parse_args()
    
    print(f"\nRunning live performance tests on port {args.port}...\n")
    run_live_performance_tests(port=args.port, duration=args.duration)
