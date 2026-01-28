# Game Modes

The game supports three different modes that can be set in the `config.json` file:

## Agent Mode
`"game_mode": "agent"`

In this mode, the client connects to a remote server to compete against other players' agents. The client uses the agent specified in the `agent` field of the configuration file.
  
## Manual Mode
`"game_mode": "manual"`

In this mode, the client connects to a remote server to compete against other players' agents. The client does not use an agent and instead controls the train manually with keyboard arrows.

## Observer Mode
`"game_mode": "observer"`

This mode will make your client an observer and you can only watch the game without interacting. If no other client connects, random agents from the `agents` list in `config.json` will compete against each other, allowing you to test and compare different versions of your agents. For better organization, it's recommended to store your agents in the "agents" folder.

## How the modes affect the client and server:

- In **Agent/Manual Mode**:
  - The client connects to the IP specified in the configuration (it can be your local IP if you want to test it locally).
  - The client initializes with the agent specified in `client.agent` (in the `config.json` file). 

- In **Observer Mode**:
  - The client connects to the IP specified in the configuration and acts as an observer, only displaying the game.
  - This allows you to watch different versions of your agents compete against each other.

## Setting up the agents for agent/manual and observer modes

In the `config.json` file, you can find the configuration for the agent/manual and observer modes.
Set up the game mode you want to play, your sciper, a nickname and the agent file name you want each of the agents to use. This agent file will be used to compete against the other agents in the agent/manual modes.
There cannot be two agents with the same nickname on the server. The length of the nickname should be between 0 and 16 characters.

For the observer mode, you don't need to specify information. If you want to join a room as an observer to watch some of your agents competing against each other, 
set up a list containing the names and agent file names in the `agents` list in `config.json` in the `server` section. You can add as many agents as you want. Make sure that the server you create has enough empty slots for them (the `nb_players_per_room` parameter).

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
            "agent_file_name": "agent.py"
        },
        {
            "nickname": "AgentExample2",
            "agent_file_name": "agent.py"
        }
    ]
}
```

## Running the client

If you are connecting to a remote server, you need to know the IP address and port of the server. If you are outside of EPFL network, you will need to use a VPN to connect to the network.

To run the client and connect to the server, replace `"127.0.0.1"` in the config file with the IP address of the server.

```bash
uv run python -m client
```

Keep in mind that events are not being processed when the pygame title bar is dragged due to a pygame limitation. Doing so
will unfortunately freeze your game and disconnect you from the server.
