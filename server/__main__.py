import sys
from common.config import Config
from server.server import Server

# Load the config file
config_file = "config.json"
if len(sys.argv) > 1:
    config_file = sys.argv[1]
config = Config.load(config_file)

# Start and run the server
server = Server(config)
server.run_game()
