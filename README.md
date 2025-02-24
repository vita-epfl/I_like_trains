# I Like Trains Game

![Thumbnail](img/thumbnail_2.png)

## Overview

I Like Trains Game is a multiplayer game where players take on the role of train operators, navigating a shared game world to collect passengers, strategically expand their trains, and skillfully avoid collisions. Built with Python and Pygame, the game employs a client-server architecture to enable networked gameplay, offering a blend of strategic decision-making and real-time reactions.

The student's objective will be to modify the agent.py file (and only this one) to remotely control a train managed by a server according to his environment.
The agent must make travel decisions for the train, as well as the game board with the Pygam Library.

## Requirements

*   Python 3.10

## Setup Instructions

Follow these steps to set up and run the game:

### 1. Create a virtual environment 

After cloning the project and entering the folder with `cd .\i_like_trains\`, enter:

```bash
python -m venv venv
```

### 2. Activate the virtual environment (every time before starting the project)

#### On Windows

```bash
.\venv\Scripts\activate
```

#### On macOS/Linux

```bash
source venv/bin/activate
```

### 3. Install the necessary dependencies

After activating the virtual environment, install the necessary dependencies:

```bash
pip install -r requirements.txt
```

### 4. Execute the client

To execute the client locally, use the following command:

```bash
python client.py
```

Same thing if you want to connect to a distant machine:
```bash
python client.py <ip_adress>
```

## Logging System

The game uses Python's built-in logging system to help with debugging and monitoring. Change the logging level in the `logging.basicConfig` function in the `agent.py` file.

Available log levels (from most to least verbose):

- DEBUG: Detailed information for debugging
- INFO: General information about game operation
- WARNING: Indicates potential issues
- ERROR: Serious problems that need attention
- CRITICAL: Critical errors that prevent the game from running

Logs are displayed in the console and include timestamps, module name, and log level.


## Agent Details

The Agent is the intelligent controller for each train in the game. It's responsible for a variety of tasks, including:

### Initialization (`__init__`)

*__The student is not supposed to modify this part__*

*   **State Initialization:** Initializes the agent's state, including:
    *   `all_trains`: A dictionary containing information about all trains in the game.
    *   `agent_name`: The unique identifier for this agent.
    *   `all_passengers`: A list of passenger positions in the game.
    *   `send_action`: A function to send actions (direction changes, respawn requests) to the server.
    *   `grid_size`, `screen_width`, `screen_height`: Game world dimensions.
    *   `directions`: A list of possible movement directions.
    *   `current_direction_index`: The agent's current movement direction.
    *   `is_dead`: A flag indicating whether the train is currently dead.
    *   `waiting_for_respawn`: A flag indicating whether the agent has requested a respawn but hasn't yet been added back to the game.
    *   `death_time`: The time when the train died.
    *   `respawn_cooldown`: The remaining time before the train can respawn.

### Collision Avoidance (`will_hit_wall`, `will_hit_train_or_wagon`)

*   **`will_hit_wall()`:** Determines if moving in a given `direction` from the current `position` will result in hitting a wall.
*   **`will_hit_train_or_wagon()`:** Determines if moving in a given `direction` from the current `position` will result in a collision with another train or a wagon.

### Passenger Management (`get_closest_passenger`, `get_direction_to_target`)

*   **`get_closest_passenger()`:** Finds the closest passenger to the train's current position (`current_pos`).
*   **`get_direction_to_target()`:** Determines the best direction to move in order to reach a given `target_pos` from the current position (`current_pos`), considering only the `valid_directions`.

### Movement and Decision Making (`get_valid_direction`, `is_opposite_direction`)

*   **`get_valid_direction()`:** Determines a valid direction for the train to move in, considering:
    *   Avoiding walls and collisions.
    *   Moving towards the closest passenger, if any.
    *   Avoiding moving in the opposite direction.
*   **`is_opposite_direction()`:** Checks if a given `new_direction` is opposite to the train's current direction.

### GUI Rendering (`draw_gui`)

*   **`draw_gui()`:** Draws the game state on the screen, including:
    *   The train and its wagons.
    *   Other trains and their wagons.
    *   Passengers.
    *   The agent's score.
    *   A "Train dead" message and respawn cooldown timer if the train is dead.

### State Update (`update`)

*__The student is not supposed to modify this part__*

*   **`update(trains, passengers, grid_size, screen_width, screen_height)`:** Updates the agent's state based on information received from the server:
    *   Updates the `all_trains`, `all_passengers`, `grid_size`, `screen_width`, and `screen_height` attributes.
    *   Handles the train's death and respawn logic:
        *   If the train is not in the `all_trains` list and is not waiting to respawn, it's marked as dead.
        *   If the train is dead, it checks if the respawn cooldown has expired.
        *   If the cooldown has expired and manual respawn is enabled, it displays a "Press SPACE to spawn" message.
        *   If the cooldown has expired and manual respawn is disabled, or if the space key is pressed, it sends a respawn request to the server.
    *   If the train is alive, it calls the `get_valid_direction` method to determine the best direction to move in and sends the corresponding action to the server.

### Communication (`send_action`)

*__The student is not supposed to modify this part__*

*   **`send_action(direction)`:** Sends the agent's action (direction change or respawn request) to the server.

In summary, the `Agent` class encapsulates all the logic required for a train to make decisions, avoid collisions, collect passengers, render its state on the screen, and communicate with the server.

