from client.client import main as client_main
from server.server import Server


def main():
    # Both, the client and server need to run on the main thread for different reasons:
    # - the server sets up signal handlers
    # - the client uses pygame
    #
    # For now, we keep both on the main thread and don't call server.run_game()
    # which we can fix later if it becomes an issue.
    Server(players_per_room=1)
    client_main()


main()
