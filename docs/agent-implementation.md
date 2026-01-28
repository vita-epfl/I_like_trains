# Agent Implementation

## Agent Class

The Agent class inherits from the `BaseAgent` class. You can find the implementation of the `BaseAgent` class in `common/base_agent.py`. 
The class is initialized with the following parameters:

- `self.nickname` : The name of the agent.
- `self.network` : The network object to handle communication.
- `self.logger` : The logger object.

And the following attributes:

- `self.game_width` and `self.game_height` : initialized later by the server but are still accessible in the program. They are the width and height of the game grid.

These parameters and attributes are not supposed to be modified. They are updated by the client, receiving the game state from the server. Modifying them may lead to a desynchronization between the information of the client and the real game state managed by the server.
On the other hand, attributes can be added to the Agent class to store additional information (related to your agent strategy).

You can check the data available in the client by using the logger:

```python
self.logger.debug(self.all_trains)
self.logger.debug(self.passengers)
self.logger.debug(self.delivery_zone)
self.logger.debug(self.best_scores)
```

or by directly checking what is returned by the `to_dict()` method in each class. For example to check the train's data format, check the method `to_dict()` in `server/train.py`. For the passenger, check `server/passenger.py`. Etc.

## Delivery Zone Data Structure

The `self.delivery_zone` attribute is a dictionary with the following structure:

```python
{
    "position": (x, y),  # Top-left corner coordinates (in pixels)
    "width": width,       # Width in pixels (extends to the right)
    "height": height      # Height in pixels (extends downward)
}
```

**Coordinate System:**
- The game uses a pixel-based coordinate system where **(0, 0) is the TOP-LEFT corner** of the game area.
- **X increases to the RIGHT**.
- **Y increases DOWNWARD**.

**Understanding the delivery zone bounds:**
- The `position` tuple `(x, y)` represents the **top-left corner** of the delivery zone.
- The zone extends from `(x, y)` to `(x + width, y + height)` (exclusive on the right/bottom edges).
- A train position `(px, py)` is **inside** the delivery zone if: `x <= px < x + width` AND `y <= py < y + height`.

**Example:**
If `delivery_zone = {"position": (100, 50), "width": 60, "height": 40}`:
- Top-left corner: `(100, 50)`
- Bottom-right corner: `(159, 89)` (since bounds are exclusive)
- Any position `(px, py)` where `100 <= px < 160` AND `50 <= py < 90` is inside the zone.

## Implementation Task

You must implement an agent that controls your train. The main method to implement in `agents/agent.py` (or any other agent file you will create in the `agents` folder) is:

```python
def get_move(self):
    """
    This method is regularly called by the client to get the next move for the train.
    """
```

- Your train exists in a 2D grid. You can tell your train to turn left, right, or continue going straight. Your code should live in [common/agents/agent.py](/common/agents/agent.py) and any additional files you might need. You can also instruct your train to drop wagons.

- Your train can drop wagons. The train will then get a speed boost and enter a boost cooldown period, during which the train cannot drop wagons. Remember, passengers are automatically dropped off in the delivery zone.

## Implementation Tips

1. For the agent:
   - Display the attributes (with `print` or using the logger) to understand their structure (self.all_trains, self.all_passengers, self.delivery_zones, etc.).
   - Start with changing the direction if the next position will hit a wall.
   - Implement an initial strategy (e.g., go towards the closest passenger).
   - Gradually add obstacle avoidance (other trains and wagons).
   - Consider handling cases where the direct path is blocked.
