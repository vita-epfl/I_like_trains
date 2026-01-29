# Performance Tests

This document describes how to run performance and scalability tests for the I Like Trains server.

## Quick Start

```bash
# Run all performance tests (server, client, live, scalability)
python -m tests.run_performance_tests

# Run only scalability tests
python -m tests.run_performance_tests --scalability-only

# Skip long-running tests for quick feedback
python -m tests.run_performance_tests --skip-live --skip-scalability
```

## Test Types

### 1. Server-Side Performance Tests
Tests core server operations like game tick processing, state serialization, and collision detection.

```bash
python -m tests.run_performance_tests --server-only
```

### 2. Client-Side Performance Tests
Tests client operations like JSON parsing, state processing, and rendering (if pygame available).

```bash
python -m tests.run_performance_tests --client-only
```

### 3. Live Integration Tests
Tests real client-server communication including connection time, ping latency, and state update frequency.

```bash
python -m tests.run_performance_tests --live-only
python -m tests.run_performance_tests --live-only -d 10  # 10 second duration
```

### 4. Scalability Tests
Tests server performance with varying numbers of players and rooms.

```bash
python -m tests.run_performance_tests --scalability-only
```

## Scalability Tests (Detailed)

The scalability test module (`test_scalability.py`) can be run directly for more control:

### Single Room Scalability
Test how the server handles increasing numbers of players in a single room:

```bash
# Test with default player counts (5, 10, 20, 50, 100)
python -m tests.test_scalability --single-room-only

# Test with specific player counts
python -m tests.test_scalability --players 5 10 20 50 100

# Test with custom duration per scenario
python -m tests.test_scalability --players 5 10 20 --duration 30
```

### Multiple Rooms Scalability
Test how the server handles multiple concurrent rooms:

```bash
# Test 20 rooms with 4 players each (80 total players)
python -m tests.test_scalability --multi-room-only

# Custom room configuration
python -m tests.test_scalability --multi-room-only --rooms 20 --per-room 4

# Test 10 rooms with 8 players each
python -m tests.test_scalability --multi-room-only --rooms 10 --per-room 8
```

### Full Scalability Suite
```bash
# Run all scalability tests
python -m tests.test_scalability

# With custom parameters
python -m tests.test_scalability --players 5 10 20 50 100 --rooms 20 --per-room 4 --duration 15
```

## Command Line Options

### Main Test Runner (`run_performance_tests.py`)

| Option | Description |
|--------|-------------|
| `-i, --iterations` | Number of iterations per test (default: 100) |
| `-d, --live-duration` | Duration for live tests in seconds (default: 5.0) |
| `--scalability-duration` | Duration for scalability tests in seconds (default: 15.0) |
| `-s, --server-only` | Only run server-side tests |
| `-c, --client-only` | Only run client-side tests |
| `-l, --live-only` | Only run live integration tests |
| `--scalability-only` | Only run scalability tests |
| `--skip-live` | Skip live integration tests |
| `--skip-scalability` | Skip scalability tests |

### Scalability Test Runner (`test_scalability.py`)

| Option | Description |
|--------|-------------|
| `-p, --port` | Base port for test servers (default: 16000) |
| `-d, --duration` | Duration for each test scenario in seconds (default: 15.0) |
| `--players` | Player counts to test in single room (default: 5 10 20 50 100) |
| `--rooms` | Number of rooms for multi-room test (default: 20, 0 to skip) |
| `--per-room` | Players per room for multi-room test (default: 4) |
| `--single-room-only` | Only run single room tests |
| `--multi-room-only` | Only run multi-room tests |
| `-s, --save` | Save summary to `tests/summaries/` with timestamp |
| `-o, --output` | Custom output directory for summary file |

## Metrics Collected

### Scalability Tests

**Basic Metrics:**
- **Connected count**: Number of clients that successfully connected
- **Game started count**: Number of clients that received game start confirmation
- **State update Hz**: Frequency of game state updates received by clients
- **Average connection time**: Time to establish connection (ms)
- **Error count**: Number of connection or communication errors

**Bandwidth Metrics:**
- **Total bytes received/sent**: Total data transferred during test
- **Bandwidth (kbps)**: Data rate in kilobits per second
- **Avg bytes per client**: Average data received per connected client

**State Update Metrics:**
- **Avg/Min/Max interval**: Time between state updates (ms)
- **Jitter (stdev)**: Variation in state update timing (ms)
- **Avg state size**: Average size of state messages (bytes)

**Latency Metrics (RTT):**
- **Avg/Min/Max RTT**: Round-trip time for ping/pong (ms)
- **RTT jitter**: Variation in round-trip time (ms)

**Per-Client Variance:**
- **Min/Max updates**: Range of state updates received across clients
- **Stdev**: Standard deviation of updates (detects unfair scheduling)

### Live Integration Tests
- **Connection time**: Time to connect a single client
- **Ping RTT**: Round-trip time for ping/pong messages
- **State update interval**: Time between state updates
- **Message throughput**: Messages sent per second

## Examples

```bash
# Quick server performance check
python -m tests.run_performance_tests --server-only -i 50

# Full scalability test with 30 second scenarios
python -m tests.test_scalability --duration 30

# Test specific high player counts
python -m tests.test_scalability --players 50 100 --rooms 0

# Test many small rooms
python -m tests.test_scalability --multi-room-only --rooms 50 --per-room 2

# Save results to file for comparison
python -m tests.test_scalability --save

# Save to custom directory
python -m tests.test_scalability --save --output ./my_results/
```

## Performance Optimizations

The server includes several performance optimizations:

1. **Dirty State Tracking**: Only sends game state when data has changed
2. **Passenger Delta Updates**: Only sends passengers that have been modified (not all passengers every frame)
3. **Message Compression**: Large messages (>1KB) are automatically compressed with zlib if compression achieves 20%+ reduction
4. **Multiprocessing Mode**: Rooms can run in separate processes to bypass Python GIL (enable with `use_multiprocessing: true` in config)