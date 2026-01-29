# I Like Trains
![GitHub Tag](https://img.shields.io/github/v/tag/vita-epfl/I_like_trains)
![Thumbnail](img/thumbnail_2.png)

## Overview

"I Like Trains" is a multiplayer, real-time, network game where trains controlled by computer programs compete. Programs are
written in Python and Pygame is used to render the playing field. Programs score points by collecting and dropping off
passengers. The more passengers a train is carrying, the longer and slower it becomes. Programs are therefore expected
to implement various strategies while avoiding collisions.

Your objective will be to modify [common/agents/agent.py](/common/agents/agent.py) file and implement logic to control
your train. You may add additional files to the directory but do not modify any existing files outside of [common/agents](/common/agents).
You can make different versions of your agent by copying the [agent.py](/common/agents/agent.py) file, renaming it and modifying it.

## Documentation

For detailed documentation, please refer to the [docs](/docs) directory:

- [Setup Instructions](/docs/setup.md) - How to set up the project
- [Game Modes](/docs/game-modes.md) - Different ways to play the game
- [Game Rules](/docs/game-rules.md) - Rules and gameplay mechanics
- [Project Structure](/docs/project-structure.md) - Overview of the codebase organization
- [Agent Implementation](/docs/agent-implementation.md) - How to implement your train agent
- [Evaluation](/docs/evaluation.md) - Submission requirements
- [Configuration](/docs/configuration.md) - Configuration options and logging
- [Version Management](/docs/version-management.md) - How to update and handle conflicts
- [Git Workflow](/docs/git-workflow.md) - Using Git for version control

## Quick Start

```bash
# Clone the repository
git clone https://github.com/vita-epfl/I_like_trains.git
cd I_like_trains

# Install uv (if not already installed)
# On macOS and Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install dependencies
uv sync
```

### Setup your config file

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

### Setup your agent file

if you don't have any existing agent.py files, copy `common/agents/agent.py.template` to `common/agents/agent.py`. You can use your graphical interface or one of the following commands:

```bash
# Linux/MacOS/Unix
cp common/agents/agent.py.template common/agents/agent.py

# Windows (Command Prompt)
copy common\agents\agent.py.template common\agents\agent.py

# Windows (PowerShell)
Copy-Item -Path common\agents\agent.py.template -Destination common\agents\agent.py
```

This will create your agent file that you'll modify to implement your train's behavior. Make sure to update the SCIPERS list in the file with your actual SCIPER numbers.

### (Optional) Start a local server for testing

You can start a local server by running `python -m server` if you want to test the client locally. This will start a server on `0.0.0.0:5555` (the host set in the configuration file config.json).
Then, open another terminal, go to the project folder, and run `python -m client config.json` to connect to the local server. This is optional, but recommended for testing before connecting to the remote server.

This allows:
- You to connect locally with your own client
- Other players to connect to your game if you share your IP address with them
- This is useful for organizing your own competitions or testing with friends


### Run the client (in a new terminal)

This will try connecting to a server. If you have started a local server, it will connect to it. 
Otherwise, if you set a distant ip and port in the config file, it will try to connect to the remote server (if running).

```bash
uv run python -m client
```

For more detailed setup instructions, see the [Setup Guide](/docs/setup.md).
