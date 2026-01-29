"""
Main runner for all performance tests.
Runs both server-side and client-side performance benchmarks.
"""

import argparse
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_server_performance import run_server_performance_tests
from tests.test_client_performance import run_client_performance_tests
from tests.test_live_performance import run_live_performance_tests
from tests.test_scalability import ScalabilityTests

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("performance_tests")


def run_all_tests(iterations: int = 100, server_only: bool = False, client_only: bool = False, 
                   live_only: bool = False, skip_live: bool = False, live_duration: float = 5.0,
                   scalability_only: bool = False, skip_scalability: bool = False,
                   scalability_duration: float = 15.0):
    """
    Run all performance tests.
    
    Args:
        iterations: Number of iterations per test
        server_only: Only run server-side tests
        client_only: Only run client-side tests
        live_only: Only run live integration tests
        skip_live: Skip live integration tests
        live_duration: Duration for live tests
        scalability_only: Only run scalability tests
        skip_scalability: Skip scalability tests
        scalability_duration: Duration for scalability tests
    """
    print("\n" + "="*70)
    print("  I LIKE TRAINS - PERFORMANCE TEST SUITE")
    print("="*70)
    print(f"  Iterations per test: {iterations}")
    print("="*70 + "\n")
    
    server_results = []
    client_results = []
    live_results = []
    scalability_results = []
    
    if not client_only and not live_only:
        print("\n" + "-"*70)
        print("  RUNNING SERVER-SIDE PERFORMANCE TESTS")
        print("-"*70 + "\n")
        server_results = run_server_performance_tests(iterations=iterations)
    
    if not server_only and not live_only and not scalability_only:
        print("\n" + "-"*70)
        print("  RUNNING CLIENT-SIDE PERFORMANCE TESTS")
        print("-"*70 + "\n")
        client_results = run_client_performance_tests(iterations=iterations)
    
    if not server_only and not client_only and not scalability_only and not skip_live:
        print("\n" + "-"*70)
        print("  RUNNING LIVE INTEGRATION TESTS")
        print("-"*70 + "\n")
        live_results = run_live_performance_tests(duration=live_duration)
    
    if scalability_only or (not server_only and not client_only and not live_only and not skip_scalability):
        print("\n" + "-"*70)
        print("  RUNNING SCALABILITY TESTS")
        print("-"*70 + "\n")
        scalability_tests = ScalabilityTests(test_duration=scalability_duration)
        scalability_results = scalability_tests.run_all_tests()
    
    # Final summary
    print("\n" + "="*70)
    print("  FINAL SUMMARY")
    print("="*70)
    
    if server_results:
        print("\n  Server-side key metrics:")
        for result in server_results:
            if any(key in result.name for key in ["Tick", "Initialization", "State Serialization"]):
                throughput = 1/result.mean if result.mean > 0 else 0
                print(f"    - {result.name}: {result.mean*1000:.4f} ms ({throughput:.0f} ops/sec)")
    
    if client_results:
        print("\n  Client-side key metrics:")
        for result in client_results:
            if any(key in result.name for key in ["Full Frame", "JSON", "State Data"]):
                throughput = 1/result.mean if result.mean > 0 else 0
                print(f"    - {result.name}: {result.mean*1000:.4f} ms ({throughput:.0f} ops/sec)")
    
    if live_results:
        print("\n  Live integration key metrics:")
        for result in live_results:
            throughput = 1/result.mean if result.mean > 0 else 0
            print(f"    - {result.name}: {result.mean*1000:.4f} ms ({throughput:.0f} ops/sec)")
    
    if scalability_results:
        print("\n  Scalability test key metrics:")
        for result in scalability_results:
            connected = result.metrics.get('connected_count', 0)
            state_hz = result.metrics.get('state_update_hz', 0)
            print(f"    - {result.name}: {connected} connected, {state_hz:.1f} Hz state updates")
    
    print("\n" + "="*70 + "\n")
    
    return {"server": server_results, "client": client_results, "live": live_results, "scalability": scalability_results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run performance tests for I Like Trains",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tests.run_performance_tests                  # Run all tests
  python -m tests.run_performance_tests -i 500           # Run with 500 iterations
  python -m tests.run_performance_tests --server-only    # Only server tests
  python -m tests.run_performance_tests --client-only    # Only client tests
  python -m tests.run_performance_tests --live-only      # Only live integration tests
  python -m tests.run_performance_tests --skip-live      # Skip live tests (faster)
        """
    )
    parser.add_argument(
        "--iterations", "-i",
        type=int,
        default=100,
        help="Number of iterations per test (default: 100)"
    )
    parser.add_argument(
        "--server-only", "-s",
        action="store_true",
        help="Only run server-side performance tests"
    )
    parser.add_argument(
        "--client-only", "-c",
        action="store_true",
        help="Only run client-side performance tests"
    )
    parser.add_argument(
        "--live-only", "-l",
        action="store_true",
        help="Only run live integration tests"
    )
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="Skip live integration tests"
    )
    parser.add_argument(
        "--scalability-only",
        action="store_true",
        help="Only run scalability tests"
    )
    parser.add_argument(
        "--skip-scalability",
        action="store_true",
        help="Skip scalability tests"
    )
    parser.add_argument(
        "--scalability-duration",
        type=float,
        default=15.0,
        help="Duration for scalability tests in seconds (default: 15.0)"
    )
    parser.add_argument(
        "--live-duration", "-d",
        type=float,
        default=5.0,
        help="Duration for live tests in seconds (default: 5.0)"
    )
    
    args = parser.parse_args()
    
    exclusive_flags = [args.server_only, args.client_only, args.live_only, args.scalability_only]
    if sum(exclusive_flags) > 1:
        print("Error: Cannot specify multiple --*-only flags together")
        sys.exit(1)
    
    run_all_tests(
        iterations=args.iterations,
        server_only=args.server_only,
        client_only=args.client_only,
        live_only=args.live_only,
        skip_live=args.skip_live,
        live_duration=args.live_duration,
        scalability_only=args.scalability_only,
        skip_scalability=args.skip_scalability,
        scalability_duration=args.scalability_duration
    )
