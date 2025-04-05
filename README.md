# I Like Trains

![Thumbnail](img/thumbnail_2.png)

## Overview

"I Like Trains" is a multiplayer, real-time, network game where trains controlled by computer programs compete. Programs are
written in Python and Pygame is used to render the playing field. Programs score points by collecting and dropping off
passengers. The more passengers a train is carrying, the longer and slower it becomes. Programs are therefore expected
to implement various strategies while avoiding collisions.

Your objective will be to modify [client/agent.py](/client/agent.py) file and implement logic to control
your train. You may add additional files to the /client directory but do not
modify any existing files, except for [client/agent.py](/client/agent.py).

## Setup Instructions

#### Prerequisites:

- Python 3.12.9
- Pygame 2.6.1

### 1. (Optional) Start a local server for testing

You can start a local server by running `python -m server` if you want to test the client locally. This will start a server on `0.0.0.0:5555`.
Then, open another terminal, go to the project folder, and run `python -m client config.json` to connect to the local server. This is optional, but recommended for testing before connecting to the remote server.

### 2. Enter your train_name and sciper in the config.json file

The file `config.json` should contain your train_name and sciper.

You cannot use the same sciper or train_name as another player already connected.

### 3. Run the client

If you are connecting to a remote server, you need to know the IP address and port of the server. If you are outside of EPFL network, you will need to use a VPN to connect to the network.

To run the client and connect to the server, replace `<ip_adress>` in the config file with the IP address of the server.

```bash
python -m client config.json
```

Keep in mind that events are not being processed when the pygame title bar is dragged due to a pygame limitation. Doing so
will unfortunately freeze your game and disconnect you from the server.

## How to Play

### 1. Launch the client

1. Launch your client: `python -m client config.json`.
2. Wait in the waiting room until all players are connected.
3. Your agent will automatically control your train.

### 2. Play the game

- The goal is to collect as many passengers (they will appear at random positions on the map), incrementing your number of wagons, and then deliver them to the delivery zone. The number above each passenger spot indicates how many passengers are at that location. You can find the list of passengers with `self.passengers` (in `client/agent.py`).

- The train cannot change its direction to the opposite, only to the left or right.

- As you pick up passengers, your train will get longer and slower.

- Once you picked up passengers, you have to go to the dropoff zone. Passengers automatically leave the train when you enter the dropoff zone. For each passenger you drop off, you score 1 point in the game.

- If you collide into another train or the walls, your train dies. You will then respawn after 10 seconds. Your code knows where all the trains are located via `self.all_trains`.

- If a player disconnects, the server will create a new AI client to control their train.

## Documentation

### Project Structure

The project is divided into two main parts:

#### 1. Server (folder `server/`)
The server is responsible for managing client connections and game synchronization. It is executed on a remote machine you can connect to.
The server files are included here so you can have a better understanding of how the management of the game works. 

- `server.py` : Manages client connections and game synchronization.
- `game.py` : Contains the main game logic.
- `train.py` : Defines the Train class and its behaviors.
- `passenger.py` : Manages passenger logic.
- `ai_client.py` : Manages AI clients (when a player disconnects).
- `delivery_zone.py` : Manages delivery zones.

#### 2. Client (folder `client/`)
The client is responsible for managing the game display and user interactions. It is executed on your machine when executing `client/client.py`.

- `client.py` : Manages server connection and the main game loop.
- `network.py` : Manages network communication with the server.
- `renderer.py` : Responsible for the graphical display of the game.
- `event_handler.py` : Manages events (keyboard inputs).
- `game_state.py` : Maintains the game state on the client side.
- `base_agent.py` : Defines the base agent class.
- `agent.py` : Controls the train's behavior.
- `ui.py` : Manages the user interface to enter train name and sciper.


### How the client data is updated from the server

1. The server hosts the room and calculates the **game state** (information from the server about the game, like the trains positions, the passengers, the delivery zones, etc.)
2. The client connects to the remote server (by default on localhost:5555)
3. The client sends its **train name** and **sciper** to the server
4. The server regularly sends the game state to the clients, and also listens to potential actions (change direction or drop wagon) from the clients to influence the game.
5. The client receives the game state in the `network.py` and updates the agent's game state from the `handle_state_data()` method in `game_state.py`.
6. This method then calls `update_agent()` (inherited by the `Agent` class from the `BaseAgent` class) to ask for a new direction the agent has to determine.
7. The `update_agent()` method then calls the method `get_direction()` to dynamically calculate the next direction the train should take according to the game state (where are the other trains, the walls, the passengers, the delivery zones, etc.) and send it to the server (`self.network.send_direction_change(direction)`).
8. The server updates the game state and the cycle continues.

### Agent class

The Agent class inherits from the `BaseAgent` class. You can find the implementation of the `BaseAgent` class in `client/base_agent.py`. 
The class is initialized with the following parameters:

- `self.agent_name` : The name of the agent.
- `self.network` : The network object to handle communication.
- `self.logger` : The logger object.
- `self.is_dead` : Whether the agent/train is currently dead or alive.

And the following attributes:

- `self.death_time` : The time when the agent last died.
- `self.respawn_cooldown` : The cooldown time before respawning.
- `self.waiting_for_respawn` : Whether the agent is waiting for respawn.
- `self.game_width` and `self.game_height` are initialized later by the server but are still accessible in the program. They are the width and height of the game grid.

This parameters and attributes are not supposed to be modified. They are updated by the client, receiving the game state from the server. Modifying them may lead to a desynchronization between the information of the client and the real game state managed by the server.
On the other hand, attributes can be added to the Agent class to store additional information (related to your agent strategy).

You can check the data available in the client by using the logger:

```python
self.logger.debug(self.all_trains)
self.logger.debug(self.all_passengers)
self.logger.debug(self.delivery_zones)
```

or by direcly checking what is returned by the `to_dict()` method in each class. For example to check the train's data format, check the method `to_dict()` in `server/train.py`. For the passenger, check `server/passenger.py`. Etc.

## Implementation Task

### Agent (agent.py)

You must implement an agent that controls your train. The main method to implement in `client/agent.py` is:

```python
def get_direction(self, game_width, game_height):
    """
    This method is regularly called by the client to get the next direction of the train.
    """
```

- Your train exists in a 2D grid. You can tell your train to turn left, right, or continue going straight. Your code should live in [client/agent.py](/client/agent.py) and any additional files you might need. You can also instruct your train to drop
wagons.

#### Using the network to send actions

The agent can also call the method `self.network.send_drop_wagon_request()` to send a request to the server to drop a wagon.
The train will then get a 0.25sec *1.5 speed boost and will enter a 10sec boost cooldown during which the train will not be able to drop wagons. Calling this method will drop one wagon from the train (costing 1 point from the train's score).
This method is not supposed to be called to deliver the passengers to the delivery zone as the delivery is automatic.

## Evaluation

On the evaluation day, you will have to send us only one agent.py file per team. You should enter all the scipers of the team members in the SCIPERS constant of the file so we can identify your team. DO NOT forget to fill it, otherwise the file will not be graded.

## Implementation Tips

1. For the agent:
   - Display the attributes (with `print` or using the logger) to understand their structure (self.all_trains, self.all_passengers, self.delivery_zones, etc.).
   - Start with changing the direction if the next position will hit a wall.
   - Implement an initial strategy (e.g., go towards the closest passenger).
   - Gradually add obstacle avoidance (other trains and wagons).
   - Consider handling cases where the direct path is blocked.

### Tools and parameters in config.json

Some constants are available in the config.json file to customize your graphical interface:
- `screen_width`: width of the game window. 
- `screen_height`: height of the game window.
- `cell_size`: size of each cell in the grid.
- `leaderboard_width`: width of the leaderboard.

Some constants are available for debugging:
- `manual_spawn`: Automatic respawn when available. False by default, otherwise the player has to press the space bar.
- `control_mode`: `manual` (by default) enables manual control of your train with keyboard arrows. `agent` enables agent automatic control.

### Logging System

The game uses Python's built-in logging system to help with debugging and monitoring. Change the logging level in the `logging.basicConfig` function at the beginning of each file from which you want to follow the logs.

Examples: `logger.debug("Debug message")`, `logger.info("Info message")`, `logger.warning("Warning message")`, `logger.error("Error message")`, `logger.critical("Critical message")`.

Available log levels (from most to least verbose):

- DEBUG: Detailed information for debugging.
- INFO: General information about game operation.
- WARNING: Indicates potential issues.
- ERROR: Serious problems that need attention.
- CRITICAL: Critical errors that prevent the game from running.

Logs are displayed in the console and include timestamps, module name, and log level.