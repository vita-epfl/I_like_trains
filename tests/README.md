# Unit Tests for I_like_trains

This folder contains the unit tests for the I_like_trains project, a multiplayer network game using UDP.

## Test Structure

Tests are organized by component:

- `test_network.py`: Tests for the NetworkManager class that handles network communications
- `test_game_state.py`: Tests for the GameState class that manages the game state
- `test_server.py`: Tests for the Server class that manages the game server
- `test_room.py`: Tests for the Room class that manages game rooms

## Prerequisites

To run the tests, you will need:

- Python 3.6+
- pytest
- pytest-mock

You can install the dependencies with:

```bash
pip install -r tests/requirements-test.txt
```

## Running the Tests

To run all tests:

```bash
pytest tests/
```

To run a specific test file:

```bash
pytest tests/test_network.py
```

To run a specific test:

```bash
pytest tests/test_network.py::TestNetworkManager::test_connect_success
```

To get more details about the tests being run:

```bash
pytest tests/ -v
```

## Test Coverage

The tests cover the main functionalities of the project, including:

1. **Network Management**:
   - Connection and disconnection
   - Sending and receiving messages
   - Server disconnection detection

2. **Game State Management**:
   - Processing state data
   - Managing trains, passengers, and delivery zones
   - Handling train death and respawning

3. **Server**:
   - Creating and managing rooms
   - Managing clients and disconnections
   - Sending pings and detecting timeouts

4. **Game Rooms**:
   - Adding and removing clients
   - Starting the game
   - Managing collisions
   - Sending game state updates

## Adding New Tests

To add new tests:

1. Create a new test file or add methods to existing test classes
2. Follow the naming convention `test_*.py` for files and `test_*` for methods
3. Use the fixtures defined in `conftest.py` to reuse mock objects
