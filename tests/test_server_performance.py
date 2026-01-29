"""
Server-side performance tests for I Like Trains.
Measures game logic, tick processing, and message handling performance.
"""

import time
import statistics
import logging
import random
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.game import Game, CELL_SIZE
from server.train import Train
from server.passenger import Passenger
from server.delivery_zone import DeliveryZone
from common.move import Move

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_server_performance")


class MockConfig:
    """Mock server configuration for testing"""
    def __init__(self):
        self.tick_rate = 60
        self.game_life_time_seconds = 60
        self.game_duration_seconds = 300
        self.grading_mode = False
        self.waiting_time_before_bots_seconds = 0
        self.agents = []
        self.seed = 42
        self.max_passengers = 3
        self.respawn_cooldown_seconds = 5.0
        self.delivery_cooldown_seconds = 0.1
        self.ai_agent_file_name = "ai_agent.py"


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
            f"  Iterations: {self.iterations}\n"
            f"  Mean:       {self.mean*1000:.4f} ms\n"
            f"  Median:     {self.median*1000:.4f} ms\n"
            f"  Std Dev:    {self.stdev*1000:.4f} ms\n"
            f"  Min:        {self.min_time*1000:.4f} ms\n"
            f"  Max:        {self.max_time*1000:.4f} ms\n"
            f"  Throughput: {1/self.mean:.2f} ops/sec\n" if self.mean > 0 else ""
        )


def dummy_cooldown_notification(nickname, cooldown, death_reason):
    """Dummy callback for cooldown notifications"""
    pass


class ServerPerformanceTests:
    """Server-side performance test suite"""

    def __init__(self, iterations: int = 100):
        self.iterations = iterations
        self.config = MockConfig()
        self.results = []

    def run_all_tests(self):
        """Run all server performance tests"""
        logger.info("Starting server-side performance tests...")
        
        self.test_game_initialization()
        self.test_train_creation()
        self.test_train_movement()
        self.test_train_collision_detection()
        self.test_passenger_spawning()
        self.test_game_state_serialization()
        self.test_tick_processing()
        self.test_multiple_trains_update()
        self.test_delivery_zone_collision()
        
        self._print_summary()
        return self.results

    def test_game_initialization(self):
        """Test game initialization performance"""
        times = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            game = Game(
                self.config,
                dummy_cooldown_notification,
                nb_players=4,
                room_id="test_room",
                seed=42
            )
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("Game Initialization", times)
        self.results.append(result)
        logger.info(str(result))

    def test_train_creation(self):
        """Test train creation performance"""
        game = Game(
            self.config,
            dummy_cooldown_notification,
            nb_players=4,
            room_id="test_room",
            seed=42
        )
        
        times = []
        for i in range(self.iterations):
            start = time.perf_counter()
            game.add_train(f"TestTrain_{i}")
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("Train Creation", times)
        self.results.append(result)
        logger.info(str(result))

    def test_train_movement(self):
        """Test single train movement/update performance"""
        game = Game(
            self.config,
            dummy_cooldown_notification,
            nb_players=4,
            room_id="test_room",
            seed=42
        )
        game.add_train("TestTrain")
        train = game.trains["TestTrain"]
        
        times = []
        for tick in range(self.iterations):
            start = time.perf_counter()
            train.update(
                game.trains,
                game.game_width,
                game.game_height,
                game.cell_size,
                tick
            )
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("Single Train Update", times)
        self.results.append(result)
        logger.info(str(result))

    def test_train_collision_detection(self):
        """Test collision detection performance with multiple trains"""
        game = Game(
            self.config,
            dummy_cooldown_notification,
            nb_players=10,
            room_id="test_room",
            seed=42
        )
        
        # Add multiple trains
        for i in range(10):
            game.add_train(f"Train_{i}")
        
        times = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            # Check collision for a position against all trains
            test_x, test_y = 200, 200
            for train in game.trains.values():
                if train.position == (test_x, test_y):
                    pass
                for wagon in train.wagons:
                    if wagon == (test_x, test_y):
                        pass
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("Collision Detection (10 trains)", times)
        self.results.append(result)
        logger.info(str(result))

    def test_passenger_spawning(self):
        """Test passenger spawning performance"""
        game = Game(
            self.config,
            dummy_cooldown_notification,
            nb_players=4,
            room_id="test_room",
            seed=42
        )
        
        times = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            passenger = Passenger(game)
            end = time.perf_counter()
            times.append(end - start)
            game.passengers.append(passenger)
        
        result = PerformanceResult("Passenger Spawning", times)
        self.results.append(result)
        logger.info(str(result))

    def test_game_state_serialization(self):
        """Test game state serialization performance"""
        game = Game(
            self.config,
            dummy_cooldown_notification,
            nb_players=4,
            room_id="test_room",
            seed=42
        )
        
        # Add some game objects
        for i in range(4):
            game.add_train(f"Train_{i}")
        for _ in range(10):
            game.passengers.append(Passenger(game))
        
        times = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            state = game.get_state()
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("Game State Serialization", times)
        self.results.append(result)
        logger.info(str(result))

    def test_tick_processing(self):
        """Test full tick processing with multiple trains and passengers"""
        game = Game(
            self.config,
            dummy_cooldown_notification,
            nb_players=4,
            room_id="test_room",
            seed=42
        )
        
        # Setup game with multiple objects
        for i in range(4):
            game.add_train(f"Train_{i}")
        for _ in range(5):
            game.passengers.append(Passenger(game))
        
        times = []
        for tick in range(self.iterations):
            start = time.perf_counter()
            
            # Simulate a tick: update all trains
            for train in game.trains.values():
                train.update(
                    game.trains,
                    game.game_width,
                    game.game_height,
                    game.cell_size,
                    tick
                )
            
            # Get dirty state (what would be sent to clients)
            dirty_state = game.get_dirty_state()
            
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("Full Tick Processing (4 trains, 5 passengers)", times)
        self.results.append(result)
        logger.info(str(result))

    def test_multiple_trains_update(self):
        """Test performance scaling with many trains"""
        train_counts = [2, 4, 8, 16, 32]
        
        for count in train_counts:
            game = Game(
                self.config,
                dummy_cooldown_notification,
                nb_players=count,
                room_id="test_room",
                seed=42
            )
            
            for i in range(count):
                game.add_train(f"Train_{i}")
            
            times = []
            for tick in range(self.iterations):
                start = time.perf_counter()
                for train in game.trains.values():
                    train.update(
                        game.trains,
                        game.game_width,
                        game.game_height,
                        game.cell_size,
                        tick
                    )
                end = time.perf_counter()
                times.append(end - start)
            
            result = PerformanceResult(f"Update {count} Trains", times)
            self.results.append(result)
            logger.info(str(result))

    def test_delivery_zone_collision(self):
        """Test delivery zone collision detection performance"""
        game = Game(
            self.config,
            dummy_cooldown_notification,
            nb_players=4,
            room_id="test_room",
            seed=42
        )
        
        delivery_zone = game.delivery_zone
        
        times = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            # Test random positions against delivery zone
            for _ in range(100):
                test_x = random.randint(0, game.game_width)
                test_y = random.randint(0, game.game_height)
                in_zone = (
                    delivery_zone.x <= test_x <= delivery_zone.x + delivery_zone.width and
                    delivery_zone.y <= test_y <= delivery_zone.y + delivery_zone.height
                )
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("Delivery Zone Collision (100 checks)", times)
        self.results.append(result)
        logger.info(str(result))

    def _print_summary(self):
        """Print a summary of all test results"""
        print("\n" + "="*70)
        print("  SERVER PERFORMANCE TEST SUMMARY")
        print("="*70)
        
        for result in self.results:
            print(f"  {result.name:45} | {result.mean*1000:8.4f} ms | {1/result.mean if result.mean > 0 else 0:8.0f} ops/sec")
        
        print("="*70 + "\n")


def run_server_performance_tests(iterations: int = 100):
    """Run server performance tests and return results"""
    tests = ServerPerformanceTests(iterations=iterations)
    return tests.run_all_tests()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run server-side performance tests")
    parser.add_argument(
        "--iterations", "-i",
        type=int,
        default=100,
        help="Number of iterations per test (default: 100)"
    )
    args = parser.parse_args()
    
    print(f"\nRunning server performance tests with {args.iterations} iterations...\n")
    run_server_performance_tests(iterations=args.iterations)
