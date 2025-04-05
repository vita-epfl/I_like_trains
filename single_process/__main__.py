import sys
from client.agent import Agent
from client.client import Client, main as client_main
from common.config import Config
from server.server import Server


def main():
    # Both, the client and server need to run on the main thread for different reasons:
    # - the server sets up signal handlers
    # - the client uses pygame
    #
    # For now, we keep both on the main thread and don't call server.run_game()
    # which we can fix later if it becomes an issue.

    # Load the config file
    config_file = "config.json"
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    config = Config.load(config_file)

    # Override players_per_room. The alternative would be to launch players_per_room clients
    # but that might be too chaotic
    config.server.players_per_room = 1

    # Enables setting breakpoints and resuming the runtime without considering the client as disconnected
    config.server.client_timeout_seconds = 86400  # 86400 seconds == 1 day
    config.client.server_timeout_seconds = 86400  # 86400 seconds == 1 day

    Server(config)

    client = Client(config)
    agent = Agent("", client.network)
    client.set_agent(agent)
    client.run()


main()
