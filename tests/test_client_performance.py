"""
Client-side performance tests for I Like Trains.
Measures rendering, state processing, and network message handling performance.
Note: Some tests require pygame to be initialized (headless mode where possible).
"""

import time
import statistics
import logging
import sys
import os
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set SDL to use dummy video driver for headless testing
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_client_performance")


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


class ClientPerformanceTests:
    """Client-side performance test suite"""

    def __init__(self, iterations: int = 100):
        self.iterations = iterations
        self.results = []
        self.pygame_available = False
        
        # Try to initialize pygame
        try:
            import pygame
            pygame.init()
            self.pygame_available = True
            self.pygame = pygame
            # Create a small test surface
            self.test_surface = pygame.Surface((800, 600))
            logger.info("Pygame initialized successfully")
        except Exception as e:
            logger.warning(f"Pygame not available for testing: {e}")

    def run_all_tests(self):
        """Run all client performance tests"""
        logger.info("Starting client-side performance tests...")
        
        self.test_json_message_parsing()
        self.test_state_data_processing()
        self.test_train_data_deserialization()
        self.test_leaderboard_sorting()
        
        if self.pygame_available:
            self.test_surface_operations()
            self.test_rect_drawing()
            self.test_text_rendering()
            self.test_full_frame_simulation()
        
        self._print_summary()
        return self.results

    def test_json_message_parsing(self):
        """Test JSON message parsing performance (simulating network messages)"""
        # Create sample game state message
        sample_state = {
            "type": "state",
            "data": {
                "trains": {
                    f"Train_{i}": {
                        "position": [100 + i * 20, 100 + i * 20],
                        "wagons": [[80 + i * 20, 100 + i * 20], [60 + i * 20, 100 + i * 20]],
                        "direction": [1, 0],
                        "score": i * 10,
                        "color": [255, 100, 100],
                        "alive": True
                    }
                    for i in range(4)
                },
                "passengers": [
                    {"position": [200 + i * 40, 200], "color": [0, 255, 0]}
                    for i in range(5)
                ],
                "delivery_zone": {"x": 300, "y": 300, "width": 100, "height": 100}
            }
        }
        json_message = json.dumps(sample_state)
        
        times = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            parsed = json.loads(json_message)
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("JSON Message Parsing", times)
        self.results.append(result)
        logger.info(str(result))

    def test_state_data_processing(self):
        """Test processing of game state data"""
        sample_data = {
            "trains": {
                f"Train_{i}": {
                    "position": [100 + i * 20, 100 + i * 20],
                    "wagons": [[80 + i * 20, 100 + i * 20], [60 + i * 20, 100 + i * 20]],
                    "direction": [1, 0],
                    "score": i * 10,
                    "color": [255, 100, 100],
                    "alive": True
                }
                for i in range(4)
            },
            "passengers": [
                {"position": [200 + i * 40, 200], "color": [0, 255, 0]}
                for i in range(5)
            ],
            "size": {"game_width": 500, "game_height": 500},
            "cell_size": 20
        }
        
        times = []
        for _ in range(self.iterations):
            # Simulate state processing like in game_state.py
            start = time.perf_counter()
            
            trains = {}
            if "trains" in sample_data:
                for name, train_data in sample_data["trains"].items():
                    trains[name] = {
                        "position": tuple(train_data.get("position", [0, 0])),
                        "wagons": [tuple(w) for w in train_data.get("wagons", [])],
                        "direction": tuple(train_data.get("direction", [1, 0])),
                        "score": train_data.get("score", 0),
                        "color": tuple(train_data.get("color", [255, 255, 255])),
                        "alive": train_data.get("alive", True)
                    }
            
            passengers = []
            if "passengers" in sample_data:
                for p_data in sample_data["passengers"]:
                    passengers.append({
                        "position": tuple(p_data.get("position", [0, 0])),
                        "color": tuple(p_data.get("color", [0, 255, 0]))
                    })
            
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("State Data Processing", times)
        self.results.append(result)
        logger.info(str(result))

    def test_train_data_deserialization(self):
        """Test train data deserialization with varying wagon counts"""
        wagon_counts = [0, 5, 10, 20, 50]
        
        for wagon_count in wagon_counts:
            train_data = {
                "position": [100, 100],
                "wagons": [[100 - i * 20, 100] for i in range(1, wagon_count + 1)],
                "direction": [1, 0],
                "score": 100,
                "color": [255, 100, 100],
                "alive": True,
                "boost_cooldown_active": False
            }
            
            times = []
            for _ in range(self.iterations):
                start = time.perf_counter()
                
                processed = {
                    "position": tuple(train_data["position"]),
                    "wagons": [tuple(w) for w in train_data["wagons"]],
                    "direction": tuple(train_data["direction"]),
                    "score": train_data["score"],
                    "color": tuple(train_data["color"]),
                    "alive": train_data["alive"]
                }
                
                end = time.perf_counter()
                times.append(end - start)
            
            result = PerformanceResult(f"Train Deserialization ({wagon_count} wagons)", times)
            self.results.append(result)
            logger.info(str(result))

    def test_leaderboard_sorting(self):
        """Test leaderboard sorting performance"""
        player_counts = [4, 10, 20, 50]
        
        for count in player_counts:
            leaderboard_data = [
                {"nickname": f"Player_{i}", "score": i * 10 + (i % 7) * 5}
                for i in range(count)
            ]
            
            times = []
            for _ in range(self.iterations):
                start = time.perf_counter()
                sorted_data = sorted(leaderboard_data, key=lambda x: x["score"], reverse=True)
                end = time.perf_counter()
                times.append(end - start)
            
            result = PerformanceResult(f"Leaderboard Sort ({count} players)", times)
            self.results.append(result)
            logger.info(str(result))

    def test_surface_operations(self):
        """Test pygame surface operations"""
        if not self.pygame_available:
            return
        
        times = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            
            # Create and fill surfaces (common rendering operations)
            surface = self.pygame.Surface((800, 600))
            surface.fill((30, 30, 50))
            
            # Blit operation
            small_surface = self.pygame.Surface((100, 100))
            small_surface.fill((255, 0, 0))
            surface.blit(small_surface, (100, 100))
            
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("Surface Operations (create, fill, blit)", times)
        self.results.append(result)
        logger.info(str(result))

    def test_rect_drawing(self):
        """Test rectangle drawing performance (train/wagon rendering)"""
        if not self.pygame_available:
            return
        
        rect_counts = [10, 50, 100, 200]
        
        for count in rect_counts:
            times = []
            for _ in range(self.iterations):
                self.test_surface.fill((30, 30, 50))
                
                start = time.perf_counter()
                for i in range(count):
                    x = (i * 23) % 700
                    y = (i * 17) % 500
                    self.pygame.draw.rect(
                        self.test_surface,
                        (255, 100 + (i % 100), 100),
                        (x, y, 20, 20)
                    )
                end = time.perf_counter()
                times.append(end - start)
            
            result = PerformanceResult(f"Draw {count} Rectangles", times)
            self.results.append(result)
            logger.info(str(result))

    def test_text_rendering(self):
        """Test text rendering performance (scores, names, etc.)"""
        if not self.pygame_available:
            return
        
        font = self.pygame.font.Font(None, 24)
        texts = [f"Player_{i}: {i * 100} pts" for i in range(10)]
        
        times = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            
            rendered_texts = []
            for text in texts:
                rendered = font.render(text, True, (255, 255, 255))
                rendered_texts.append(rendered)
            
            # Blit all texts
            for i, rendered in enumerate(rendered_texts):
                self.test_surface.blit(rendered, (10, 10 + i * 25))
            
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("Text Rendering (10 labels)", times)
        self.results.append(result)
        logger.info(str(result))

    def test_full_frame_simulation(self):
        """Test a full frame rendering simulation"""
        if not self.pygame_available:
            return
        
        font = self.pygame.font.Font(None, 24)
        
        # Simulate game objects
        trains = [
            {"position": (100 + i * 50, 100), "wagons": [(80 + i * 50, 100), (60 + i * 50, 100)], "color": (255, 100, 100)}
            for i in range(4)
        ]
        passengers = [{"position": (200 + i * 40, 300), "color": (0, 255, 0)} for i in range(5)]
        delivery_zone = {"x": 400, "y": 400, "width": 100, "height": 100}
        leaderboard = [{"nickname": f"Player_{i}", "score": 100 - i * 10} for i in range(4)]
        
        times = []
        for _ in range(self.iterations):
            start = time.perf_counter()
            
            # Clear screen
            self.test_surface.fill((30, 30, 50))
            
            # Draw delivery zone
            self.pygame.draw.rect(
                self.test_surface,
                (0, 100, 200),
                (delivery_zone["x"], delivery_zone["y"], delivery_zone["width"], delivery_zone["height"])
            )
            
            # Draw passengers
            for p in passengers:
                self.pygame.draw.rect(
                    self.test_surface,
                    p["color"],
                    (p["position"][0], p["position"][1], 20, 20)
                )
            
            # Draw trains and wagons
            for train in trains:
                # Draw wagons first
                for wagon in train["wagons"]:
                    self.pygame.draw.rect(
                        self.test_surface,
                        (200, 80, 80),
                        (wagon[0], wagon[1], 20, 20)
                    )
                # Draw train head
                self.pygame.draw.rect(
                    self.test_surface,
                    train["color"],
                    (train["position"][0], train["position"][1], 20, 20)
                )
            
            # Draw leaderboard
            for i, entry in enumerate(leaderboard):
                text = font.render(f"{entry['nickname']}: {entry['score']}", True, (255, 255, 255))
                self.test_surface.blit(text, (600, 10 + i * 25))
            
            end = time.perf_counter()
            times.append(end - start)
        
        result = PerformanceResult("Full Frame Simulation", times)
        self.results.append(result)
        logger.info(str(result))

    def _print_summary(self):
        """Print a summary of all test results"""
        print("\n" + "="*70)
        print("  CLIENT PERFORMANCE TEST SUMMARY")
        print("="*70)
        
        for result in self.results:
            throughput = 1/result.mean if result.mean > 0 else 0
            print(f"  {result.name:45} | {result.mean*1000:8.4f} ms | {throughput:8.0f} ops/sec")
        
        print("="*70 + "\n")
        
        # FPS estimation for full frame
        for result in self.results:
            if "Full Frame" in result.name:
                estimated_fps = 1 / result.mean if result.mean > 0 else 0
                print(f"  Estimated max FPS (rendering only): {estimated_fps:.0f}")
                break

    def cleanup(self):
        """Clean up pygame resources"""
        if self.pygame_available:
            self.pygame.quit()


def run_client_performance_tests(iterations: int = 100):
    """Run client performance tests and return results"""
    tests = ClientPerformanceTests(iterations=iterations)
    results = tests.run_all_tests()
    tests.cleanup()
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run client-side performance tests")
    parser.add_argument(
        "--iterations", "-i",
        type=int,
        default=100,
        help="Number of iterations per test (default: 100)"
    )
    args = parser.parse_args()
    
    print(f"\nRunning client performance tests with {args.iterations} iterations...\n")
    run_client_performance_tests(iterations=args.iterations)
