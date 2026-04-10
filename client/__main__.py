import asyncio
import logging
import sys

from client.client import Client
from common.config import Config

# Client entrypoint. The client is meant to be as stateless as possible.
# The client does however store:
# - the connection state to the server (connecting, connected, disconnected)
# - the RoomState since that is not sent over the network at every game tick
#
# The client code is single threaded, single process. Async/await co-routines
# are used to concurrently process network messages and update the UI.

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

# Load the config file
config_file: str = "config.json"
if len(sys.argv) > 1:
    config_file = sys.argv[1]
config: Config = Config.load(config_file)

# Create the client, agent, and start the client
client: Client = Client(config)
asyncio.run(client.run())
