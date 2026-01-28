# Game Rules

- The goal is to collect as many passengers (they will appear at random positions on the map), incrementing your number of wagons, and then deliver them to the delivery zone (in light red). The number above each passenger spot indicates how many passengers are at that location. You can find the list of passengers with `self.passengers` (in your `common/agents/agent.py`).

- The train cannot change its direction to the opposite, only to the left or right.

- As you pick up passengers, your train will get longer and slower.

- Once you picked up passengers, you have to go to the dropoff zone. Passengers automatically leave the train when you enter the dropoff zone. For each passenger you drop off, you score 1 point in the game.

- If you collide into another train or the walls, your train dies. You will then respawn after 10 seconds. Your code knows where all the trains are located via `self.all_trains`.

- If a player disconnects, the server will create a new AI client to control their train.

## Playing Options

There are several ways to play and test your agent:

1. **Connect to the remote server with two clients**:
   - Start two clients in two different terminals using `uv run python -m client`
   - Both clients will join the same room
   - **Pros**: Tests your agent in a real network environment similar to the final evaluation
   - **Cons**: Requires the remote server to be available and not busy

2. **Run a local server + two clients**:
   - Start a local server in one terminal: `uv run python -m server`
   - Start two clients in two different terminals: `uv run python -m client`
   - **Pros**: Allows testing without depending on remote server availability, and an easier debugging process
   - **Cons**: Requires managing multiple terminals

3. **Run a local server + an observer client**:
   - Configure `config.json` to use `"game_mode": "observer"`
   - Run `uv run python -m client`
   - **Pros**: Easiest way to test multiple agent implementations against each other and choose the best one
   - **Cons**: Doesn't test network robustness of your implementation

## Evaluation Setup

During the final evaluation:
- Your agent will be tested in an environment similar to option 3
- Your agent file will be evaluated against our bots of different levels. The more bots you beat, the better your agent will be ranked.
