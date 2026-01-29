import sys
from common.config import Config
from client.client import Client

# Load the config file
config_file: str = "config.json"
if len(sys.argv) > 1:
    config_file = sys.argv[1]
config: Config = Config.load(config_file)

# Create the client, agent, and start the client
client: Client = Client(config)
client.run()
