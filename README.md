# I Like Trains

![Thumbnail](img/thumbnail_2.png)

## Overview

"I Like Trains" is a multiplayer, real-time, network game where trains controlled by computer programs compete. Programs are
written in Python and Pygame is used to render the playing field. Programs score points by collecting and dropping off
passengers. The more passengers a train is carrying, the longer and slower it becomes. Programs are therefore expected
to implement various strategies while avoiding collisions.

Your objective will be to modify [common/agents/agent.py](/common/agents/agent.py) file and implement logic to control
your train. You may add additional files to the directory but do not modify any existing files outside of [common/agents](/common/agents).
You can make different versions of your agent by copying the [agent.py](/common/agents/agent.py) file, renaming it and modifying it.

## Setup Instructions

#### Prerequisites:

- Python 3.12.9


### 1. Clone this repo

```bash
git clone https://github.com/vita-epfl/I_like_trains.git
cd I_like_trains
```

You can also use VS Code to clone the repo.

Make sure you open the root folder (I_like_trains) in VS Code. If you have installed `'code'`, you can do `code .`.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup your config file

Copy `config.json.template` to `config.json`. You can use your graphical interface or one of the following commands:

```bash
# Linux/MacOS/Unix
cp config.json.template config.json

# Windows (Command Prompt)
copy config.json.template config.json

# Windows (PowerShell)
Copy-Item -Path config.json.template -Destination config.json
```

You can leave `config.json` as-is for now. Later, you will
want to adjust the config file if you want to connect to the lab's server
or run multiple agents. You will also need to adjust the config if you
want to play with the keyboard against your agent.

### 4. (Optional) Start a local server for testing

You can start a local server by running `python -m server` if you want to test the client locally. This will start a server on `0.0.0.0:5555` (the host set in the configuration file).
Then, open another terminal, go to the project folder, and run `python -m client config.json` to connect to the local server. This is optional, but recommended for testing before connecting to the remote server.

This allows:
- You to connect locally with your own client
- Other players to connect to your game if you share your IP address with them
- This is useful for organizing your own competitions or testing with friends

### 5. Select a Game Mode

The game supports three different modes that can be set in the `config.json` file:

- **Agent Mode** (`"game_mode": "agent"`): In this mode, the client connects to a remote server to compete against other players' agents. The client uses the agent specified in the `agent` field of the configuration file.
  
- **Manual Mode** (`"game_mode": "manual"`): In this mode, the client connects to a remote server to compete against other players' agents. The client does not use an agent and instead controls the train manually with keyboard arrows.

- **Observer Mode** (`"game_mode": "observer"`): This mode will make your client an observer and you can only watch the game without interacting. If no other client connects, random agents from the `agents` list in `config.json` will compete against each other, allowing you to test and compare different versions of your agents. For better organization, it's recommended to store your agents in the "agents" folder.

How the modes affect the client and server:

- In **Agent/Manual Mode**:
  - The client connects to the IP specified in the configuration (it can be your local IP if you want to test it locally).
  - The client initializes with the agent specified in `client.agent` (in the `config.json` file). 

- In **Observer Mode**:
  - The client connects to the IP specified in the configuration and acts as an observer, only displaying the game.
  - This allows you to watch different versions of your agents compete against each other.

Modify the game mode in "client" according to the mode you want to use.

### 6. Set up the agents for agent/manual and observer modes

In the `config.json` file, you can find the configuration for the agent/manual and observer modes.
Set up the game mode you want to play, your sciper, a train name, and the name of the agent file. This agent file will be used to compete against the other agents in the agent/manual modes.

For the observer mode, you don't need to specify information. If you want to join a room as an observer to watch some of your agents competing against each other, 
set up a list containing the names and agent file names in the `agents` list in `config.json` in the `server` section. You can add as many agents as you want. Make sure that the server you create has enough empty slots for them (the `nb_clients_per_room` parameter).

Example configuration in `config.json`:
```json
"client": {
    "game_mode": "agent",
    "sciper": "000000",
    "agent": {
        "nickname": "Player",
        "agent_file_name": "agent.py"
    },
    "manual": {
        "nickname": "Keyboard"
    }
},
"server": {
    "agents": [
        {
            "nickname": "AgentExample1",
            "agent_file_name": "agent_example1.py"
        },
        {
            "nickname": "AgentExample2",
            "agent_file_name": "agent_example2.py"
        }
    ]
}
```

### 7. Run the client

If you are connecting to a remote server, you need to know the IP address and port of the server. If you are outside of EPFL network, you will need to use a VPN to connect to the network.

To run the client and connect to the server, replace `<ip_adress>` in the config file with the IP address of the server.

```bash
python -m client
```

Keep in mind that events are not being processed when the pygame title bar is dragged due to a pygame limitation. Doing so
will unfortunately freeze your game and disconnect you from the server.

## Playing Options

There are several ways to play and test your agent:

1. **Connect to the remote server with two clients**:
   - Start two clients in two different terminals using `python -m client`
   - Both clients will join the same room
   - **Pros**: Tests your agent in a real network environment similar to the final evaluation
   - **Cons**: Requires the remote server to be available and not busy

2. **Run a local server + two clients**:
   - Start a local server in one terminal: `python -m server`
   - Start two clients in two different terminals: `python -m client`
   - **Pros**: Allows testing without depending on remote server availability, and an easier debugging process
   - **Cons**: Requires managing multiple terminals

3. **Run a local server + an observer client**:
   - Configure `config.json` to use `"game_mode": "observer"`
   - Run `python -m client`
   - **Pros**: Easiest way to test multiple agent implementations against each other and choose the best one
   - **Cons**: Doesn't test network robustness of your implementation

### Evaluation Setup

During the final evaluation:
- Your agent will be tested in an environment similar to option 3
- Your agent file will be evaluated against our bots of different levels. The more bots you beat, the better your agent will be ranked.

## Game rules

- The goal is to collect as many passengers (they will appear at random positions on the map), incrementing your number of wagons, and then deliver them to the delivery zone. The number above each passenger spot indicates how many passengers are at that location. You can find the list of passengers with `self.passengers` (in your `common/agents/agent.py`).

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
- `game.py` : Contains the main game logic. Each train moves by self.cell_size each time the get_move() method is called.
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
- `ui.py` : Manages the user interface to enter train name and sciper.

### 3. Agents (folder `common/agents/`)
The agents are the files that control the behavior of the train. You can find the implementation of the `BaseAgent` class in `common/base_agent.py`. 

The agents are stored in the `common/agents` folder. You can add your own agent by creating a new file in this folder. The agent file should contain a class that inherits from the `BaseAgent` class and implements the `get_move()` method. You can name them as you want and import them in the config to test them.

### How the client data is updated from the server

1. The server hosts the room and calculates the **game state** (information from the server about the game, like the trains positions, the passengers, the delivery zones, etc.)
2. The client connects to the remote server (by default on localhost:5555)
3. The client sends its **train name** and **sciper** to the server
4. The server regularly sends the game state to the clients, and also listens to potential actions (change direction or drop wagon) from the clients to influence the game.
5. The client receives the game state in the `network.py` and updates the agent's game state from the `handle_state_data()` method in `game_state.py`.
6. This method then calls `update_agent()` (inherited by the `Agent` class from the `BaseAgent` class) to ask for a new direction the agent has to determine.
7. The `update_agent()` method then calls the method `get_move()` to dynamically calculate the next direction the train should take according to the game state (where are the other trains, the walls, the passengers, the delivery zones, etc.) and send it to the server.
8. The server updates the game state and the cycle continues.

### Agent class

The Agent class inherits from the `BaseAgent` class. You can find the implementation of the `BaseAgent` class in `common/base_agent.py`. 
The class is initialized with the following parameters:

- `self.nickname` : The name of the agent.
- `self.network` : The network object to handle communication.
- `self.logger` : The logger object.

And the following attributes:

- `self.game_width` and `self.game_height` : initialized later by the server but are still accessible in the program. They are the width and height of the game grid.

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

You must implement an agent that controls your train. The main method to implement in `agents/agent.py` (or any other agent file you will create in the `agents` folder) is:

```python
def get_move(self):
    """
    This method is regularly called by the client to get the next move for the train.
    """
```

- Your train exists in a 2D grid. You can tell your train to turn left, right, or continue going straight. Your code should live in [common/agents/agent.py](/common/agents/agent.py) and any additional files you might need. You can also instruct your train to drop wagons.

- Your train can drop wagons. The train will then get a speed boost and enter a boost cooldown period, during which the train cannot drop wagons. Remember, passengers are automatically dropped off in the delivery zone.

## Evaluation

On the evaluation day, you will need to submit:
1. Your `agent.py` file with your implementation
2. Any additional files you created to organize your code
3. An updated `requirements.txt` if you installed additional packages

Make sure to enter all the scipers of your team members in the SCIPERS constant at the top of the `agent.py` file so we can identify your team. DO NOT forget to fill it, otherwise your submission will not be graded.

We encourage you to use additional files to properly structure your code if needed. Just ensure that your main logic is implemented in the `agent.py` file and that any additional files are properly imported.

If you installed additional packages, you can generate an updated requirements.txt file by running:
```
pip freeze > requirements.txt
```

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
- `leaderboard_width`: width of the leaderboard.

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

## Configuration Files

The game's configuration is managed through a structured mapping system defined in the following files:

- `common/config.py`: The main configuration class that loads and validates the JSON configuration file.
- `common/client_config.py`: Contains all client-specific configuration options like connection details, display settings, game mode, and timeout values.
- `common/server_config.py`: Contains all server-specific configuration options like room size, game rules, respawn times, and AI agent settings.

Students are encouraged to read these files to understand what each configuration option does and its default value. The configuration system uses Pydantic models to provide clear documentation, type validation, and default values for all settings.

## Version Management and Updates

### Checking Your Version

To ensure you have the latest version of the project:

1. **For Git users**:
   ```bash
   # Check your current commit hash
   git rev-parse HEAD
   
   # Check for updates without applying them
   git fetch origin
   git log HEAD..origin/main --oneline
   ```
   If the second command shows any commits, your local version is behind the remote repository.

2. **For archive users** (zip/tar.gz):
   - Check the download date of your archive
   - Visit the course website or repository page to see if a newer version is available

### Updating Your Project

1. **For Git users**:
   ```bash
   # First, backup your work (especially your agent files and config.json)
   cp -r common/agents/your_agent.py common/agents/your_agent_backup.py
   cp config.json config.json.backup
   
   # Then pull the latest changes
   git pull origin main
   ```

2. **For archive users**:
   - Download the latest archive
   - Extract it to a new directory
   - Copy your agent files and configuration from the old directory to the new one

### Handling Conflicts

When updating, you might encounter conflicts, especially if you've modified files that were also updated in the repository.

1. **For `config.json` conflicts**:
   - To avoid conflicts, consider keeping a separate configuration file (e.g., `my_config.json`) with your personal settings
   - Use this file for your development and only update the original `config.json` when necessary
   - Alternatively, only modify the specific sections you need (like your agent configuration) and leave the rest unchanged

2. **For other file conflicts**:
   - You should generally not modify the core game files outside the designated areas
   - If you encounter conflicts in these files, you may need assistance from a TA
   - In Git, you can see which files have conflicts with `git status`

### Backing Up Your Work

Regular backups are essential to prevent data loss:

- **Manual backups**: Regularly copy your important files (especially your agent implementations) to a separate location
- **Version control**: If using Git, commit your changes frequently to track your progress
- **Automated backups**: Use your operating system's backup features (Time Machine on macOS, File History on Windows) for regular automated backups
- **Cloud storage**: Consider using cloud storage services for an additional layer of protection

**Important**: Always back up your work before updating to a new version of the project.
