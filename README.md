# I Like Trains Game

![Thumbnail](img/thumbnail_2.png)

## Overview

I Like Trains Game is a multiplayer game where players take on the role of train operators, navigating a shared game world to collect passengers, strategically expand their trains, and skillfully avoid collisions. Built with Python and Pygame, the game employs a client-server architecture to enable networked gameplay, offering a blend of strategic decision-making and real-time reactions.

## Requirements

*   Python 3.10

## Setup Instructions

Follow these steps to set up and run the game:

### 1. Create a virtual environment (do this once after cloning the project)

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

To execute the server, use the following command:

```bash
python server/server.py
```

To execute the client, use the following command:

```bash
python client.py
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

## Simulate a server with multiple clients

Run the following command with the wished number of clients (need to be hosted locally). This program launches a local server and clients.

To simulate 10 clients:
```bash
'.\simulate_clients.ps1' -numClients 10 
```