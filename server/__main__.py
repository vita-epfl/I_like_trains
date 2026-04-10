import asyncio
import logging
import sys
from common.config import Config
from server.server import Server

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

# Load the config file
config_file = "config.json"
if len(sys.argv) > 1:
    config_file = sys.argv[1]
config = Config.load(config_file)

# Start and run the server
server = Server(config)
asyncio.run(server.run())
