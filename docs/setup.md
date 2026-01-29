# Setup Instructions

## Prerequisites:

- Python 3.12.9

## 1. Clone this repo

```bash
git clone https://github.com/vita-epfl/I_like_trains.git
cd I_like_trains
```

You can also use VS Code to clone the repo.

Make sure you open the root folder (I_like_trains) in VS Code. If you have installed `'code'`, you can do `code .`.

## 2. Install uv and dependencies

First, install uv if you don't have it already:

```bash
# On macOS and Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then install the project dependencies:

```bash
uv sync
```

## 3. Setup your config file

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

## 4. Setup your agent file

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

## 5. (Optional) Start a local server for testing

You can start a local server by running `uv run python -m server` if you want to test the client locally. This will start a server on `0.0.0.0:5555` (the host set in the configuration file).
Then, open another terminal, go to the project folder, and run `uv run python -m client config.json` to connect to the local server. This is optional, but recommended for testing before connecting to the remote server.

This allows:
- You to connect locally with your own client
- Other players to connect to your game if you share your IP address with them
- This is useful for organizing your own competitions or testing with friends
