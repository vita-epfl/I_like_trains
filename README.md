# I ❤️ Buses
![GitHub Tag](https://img.shields.io/github/v/tag/vita-epfl/I_like_trains)
![Thumbnail](img/thumbnail.png)

## Overview

"I ❤️ Buses" is a multiplayer network game where buses controlled by computer programs compete to pick up
passengers and bring them to their destinations.

Programs are written in Python and Pygame is used to render the playing field.

This version is a rewrite based on Adrien's work on I-like-trains.


## Code layout

### Client

The client code lives in `client/`. The code entrypoint (where code execution begins) is `client/__main__.py`. The client has two main files, `client/client.py` and `client/renderer.py`.

`client/renderer.py` contains the `Renderer` class, which uses pygame-ce to display the UI.

`client/client.py` contains the `Client` class. It is responsible for initializing `Renderer`, the agent, and connecting to the server. `Client` then coordinates updating the `Renderer`'s state and calling the agent's
`get_move()` method (technically, `async_get_move()` is awaited).

### Server

The server code lives in `server/`. The code entrypoint is `server/__main__.py`. The server contains three main files, `server/server.py`, `server/room.py`, and `server/game.py`.

`server/server.py` sets up the server and waits for client connections. It manages assigning
clients to rooms.

`server/room.py` manages waiting for a room to be reayd to start. The code also coordinates sending and receiving messages from each player. It also contains code to load the map and local agents.

`server/game.py` contains the code to initialize the game field. It contains code to spawn passengers and buses. It also contains the code to update the game state given a move.

### Common

The code in `common/` is shared between the client and server. It contains shared datastructures (`common/messages.py`, `common/state.py`, and `common/config.py`).

`common/agents/` contains the agent files.