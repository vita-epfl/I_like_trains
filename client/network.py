"""
Network manager class for the game "I Like Trains"
Handles all network communications between client and server
"""

import socket
import json
import logging
import threading
import time

from common.version import EXPECTED_CLIENT_VERSION


# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("client.network")


class NetworkManager:
    """Class responsible for client network communications"""

    def __init__(self, client, host, port=5555):
        """Initialize network manager with client reference"""
        self.client = client
        self.host = host
        self.port = port
        self.socket = None
        self.running = True
        self.receive_thread = None
        self.last_ping_time = 0

    def connect(self):
        """Establish connection with server"""
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Set socket timeout to detect server disconnection
            # self.socket.settimeout(3.0)  # 3 seconds timeout
            # Bind to any available port on client side (required for receiving in UDP)
            self.socket.bind(("0.0.0.0", 0))
            # Store server address for sending
            self.server_addr = (self.host, self.port)

            # Log successful connection with local client port information
            local_ip, local_port = self.socket.getsockname()
            logger.info(
                f"Successfully connected to server at {self.host}:{self.port} from local {local_ip}:{local_port}"
            )

            self.last_ping_time = time.time()

            # Start receive thread
            self.receive_thread = threading.Thread(target=self.receive_game_state)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            return True
        except Exception as e:
            logger.error(f"Failed to create UDP socket: {e}")
            return False

    def disconnect(self, stop_client=False):
        """Close connection with server"""
        self.running = False
        if stop_client:
            self.client.running = False

            # Afficher un message d'erreur si la déconnexion est due à un timeout du serveur
            # On laisse le client gérer l'affichage du message et la fermeture
            logger.warning("Server disconnection detected. Stopping client.")

        if self.socket:
            # Envoyer un message à nous-même pour débloquer le recvfrom
            if hasattr(self, "server_addr"):
                try:
                    # Obtenir l'adresse locale du socket
                    local_addr = self.socket.getsockname()
                    # Envoyer un message vide à nous-même pour débloquer le recvfrom
                    dummy_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    dummy_socket.sendto(b"", local_addr)
                    dummy_socket.close()
                except Exception as e:
                    if "10049" in str(e):
                        pass
                    else:
                        logger.debug(f"Error sending dummy packet: {e}")

            self.socket.close()
            self.socket = None  # Set to None after closing
            logger.info("UDP socket closed")

    def send_message(self, message):
        """Send message to server"""
        if not self.socket:
            logger.error("Cannot send message: UDP socket not created")
            self.disconnect(True)
            return False

        try:
            # Serialize message to JSON and send to server address
            serialized = json.dumps(message) + "\n"
            bytes_sent = self.socket.sendto(serialized.encode(), self.server_addr)
            return bytes_sent > 0
        except ConnectionResetError:
            return False
        except socket.error as e:
            # Don't log socket errors
            if "10054" in str(e):
                pass
            elif "10038" in str(e):
                pass
            else:
                logger.error(f"Failed to send UDP message: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send UDP message: {e}")
            return False

    def receive_game_state(self):
        """Thread that receives game state updates from the server"""
        # Create a custom trace level that's lower than debug
        # TRACE_LEVEL = 5  # Lower than DEBUG which is 10
        # logging.addLevelName(TRACE_LEVEL, "TRACE")

        # def trace(self, message, *args, **kwargs):
        #     if self.isEnabledFor(TRACE_LEVEL):
        #         self._log(TRACE_LEVEL, message, args, **kwargs)

        # logging.Logger.trace = trace

        while self.running:
            try:
                # Wait for data from the server
                if self.socket is None:
                    logger.debug("Socket closed, exiting receive thread")
                    break

                # Define a timeout to periodically check self.running
                # Use a shorter timeout to ensure we don't miss pings, especially when train is dead
                self.socket.settimeout(0.1)

                # Check if we've received a ping recently
                current_time = time.time()
                if (
                    current_time - self.last_ping_time
                    > self.client.config.server_timeout_seconds
                ):
                    logger.warning(
                        f"Server hasn't sent a ping for {self.client.config.server_timeout_seconds} seconds, disconnecting"
                    )
                    # Disconnect the client
                    self.disconnect(stop_client=True)
                    break

                # For UDP, we use recvfrom which returns the data and address
                data, addr = self.socket.recvfrom(65536)

                if not data:
                    continue

                # Process all messages in the packet
                messages = data.decode().split("\n")
                for message in messages:
                    if not message:
                        continue

                    try:
                        message_data = json.loads(message)
                        message_type = message_data.get("type")

                        if message_type == "state":
                            self.client.handle_state_data(message_data["data"])

                        elif message_type == "spawn_success":
                            self.client.is_dead = False
                            self.client.waiting_for_respawn = False

                        elif message_type == "game_started_success":
                            logger.info("Game has started")
                            self.client.in_waiting_room = False

                        elif message_type == "ping":
                            # Respond to ping with pong
                            self.send_message({"type": "pong"})
                            self.last_ping_time = time.time()

                        elif message_type == "pong":
                            # Mark that we received a response to our ping
                            self.client.ping_response_received = True

                        elif message_type == "game_status":
                            self.client.handle_game_status(message_data)

                        elif message_type == "join_success":
                            expected_version = message_data["expected_version"]
                            if (expected_version != EXPECTED_CLIENT_VERSION):
                                logger.error(f"Client version {EXPECTED_CLIENT_VERSION} does not match server version {expected_version}. Please update your client.")
                                self.disconnect()
                            
                        elif message_type == "drop_wagon_success":
                            self.client.handle_drop_wagon_success(message_data)
                        elif message_type == "drop_wagon_failed":
                            pass

                        elif message_type == "leaderboard":
                            self.client.handle_leaderboard_data(message_data["data"])

                        elif message_type == "waiting_room":
                            self.client.handle_waiting_room_data(message_data["data"])

                        elif message_type == "name_check":
                            if message_data["available"]:
                                logger.info(
                                    f"Name available: {message_data['available']}"
                                )
                            else:
                                logger.error(
                                    f"Name available: {message_data['available']}"
                                )
                            self.client.name_check_result = message_data.get(
                                "available", False
                            )
                            self.client.name_check_received = True

                        elif message_type == "sciper_check":
                            self.client.sciper_check_result = message_data.get(
                                "available", False
                            )
                            self.client.sciper_check_received = True
                            if message_data["available"]:
                                logger.info(
                                    f"Sciper available: {message_data['available']}"
                                )
                            else:
                                logger.error(
                                    f"Sciper available: {message_data['available']}"
                                )

                        elif message_type == "best_score":
                            logger.info(
                                f"Your best score: {message_data['best_score']}"
                            )

                        elif message_type == "death":
                            self.client.handle_death(message_data)

                        elif message_type == "disconnect":
                            logger.warning(
                                f"Received disconnect request: {message_data['reason']}"
                            )
                            self.disconnect(stop_client=True)
                            return

                        elif message_type == "game_over":
                            logger.info("Game is over. Received final scores.")
                            self.client.handle_game_over(message_data["data"])

                            # Disconnect from server after a short delay
                            def disconnect_after_delay():
                                time.sleep(
                                    2
                                )  # Wait 2 seconds to ensure all final data is received
                                logger.info("Disconnecting from server after game over")
                                self.disconnect()

                            disconnect_thread = threading.Thread(
                                target=disconnect_after_delay
                            )
                            disconnect_thread.daemon = True
                            disconnect_thread.start()

                        elif message_type == "error":
                            logger.error(
                                f"Received error from server: {message_data.get('message', 'Unknown error')}"
                            )

                        elif message_type == "initial_state":
                            self.client.handle_initial_state(message_data["data"])
                        else:
                            logger.warning(f"Unknown message type: {message_type}")
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received: {message}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")

            except socket.timeout:
                # Don't log timeout errors at all to avoid spam
                # logger.trace("Socket timeout in receive_game_state, continuing to listen")
                continue
            except Exception as e:
                # Log other errors but don't disconnect
                if "timed out" in str(e):
                    # This is redundant with the socket.timeout catch above, but kept for safety
                    # logger.trace("Socket timeout in receive_game_state, continuing to listen")
                    continue
                else:
                    logger.error(f"Error in receive_game_state thread: {e}")

    def verify_connection(self):
        """Verify that the connection to the server is actually running on the specified port
        by sending a name check request and waiting for a response.
        Returns True if the server responds, False otherwise.
        """
        if not self.socket:
            logger.error("Cannot verify connection: UDP socket not created")
            return False

        try:
            # Reset name check variables
            self.client.name_check_received = False


            # Send a ping request (this is allowed for unregistered clients)
            check_message = {"type": "ping"}
            success = self.send_message(check_message)

            if not success:
                logger.error("Failed to send ping message")
                return False

            # Wait for the name check response (which will be handled by receive_game_state thread)
            timeout = 2.0  # 2 second timeout
            start_time = time.time()

            # Wait for name check response
            while (
                not self.client.ping_response_received
                and time.time() - start_time < timeout
            ):
                time.sleep(0.1)

            if not self.client.ping_response_received:
                logger.error(
                    f"Timeout waiting for name check response from server at {self.host}:{self.port}"
                )
                return False

            # If we get here, we received a response
            return True

        except Exception as e:
            logger.error(f"Error verifying connection: {e}")
            return False

    def send_agent_ids(self, nickname, agent_sciper, game_mode):
        """Send agent name and sciper to server"""
        message = {
            "type": "agent_ids",
            "nickname": nickname,
            "agent_sciper": agent_sciper,
            "game_mode": game_mode,
        }
        return self.send_message(message)

    def send_direction_change(self, direction):
        """Send direction change to server"""
        message = {"action": "direction", "direction": direction}
        return self.send_message(message)

    def send_spawn_request(self):
        """Send spawn request to server"""
        message = {"action": "respawn"}
        return self.send_message(message)

    def send_drop_wagon_request(self):
        """Send request to drop passenger"""
        message = {"action": "drop_wagon"}
        return self.send_message(message)
