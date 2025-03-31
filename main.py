"""
Main entry point for the game "I Like Trains"
"""

import sys
import logging
from client.client import Client
from client.agent import Agent

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("main")

# Default host
DEFAULT_HOST = "localhost"


def main():
    """Main function"""
    # Check if an IP address was provided as an argument
    host = DEFAULT_HOST
    if len(sys.argv) > 1:
        host = sys.argv[1]

    logger.info(f"Connecting to server: {host}")

    # Create the client
    client = Client(host)

    # Create the agent with a temporary name (will be replaced by user input)
    agent = Agent("", client.network)

    # Set the agent for the client
    client.set_agent(agent)

    # Start the client
    try:
        client.run()
    except KeyboardInterrupt:
        logger.info("Client stopped by user")
    except Exception as e:
        logger.error(f"Error during client execution: {e}")
        raise e
    finally:
        logger.info("Client closed")


if __name__ == "__main__":
    main()
