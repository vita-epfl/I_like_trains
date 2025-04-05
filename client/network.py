"""
Network manager class for the game "I Like Trains"
Handles all network communications between client and server
"""

import socket
import json
import logging
import threading
import time


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
            logger.info(f"UDP socket created for server at {self.host}:{self.port}")

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
            try:
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
            except Exception as e:
                logger.error(f"Error closing UDP socket: {e}")
                self.socket = None  # Still set to None even if there's an error

    def send_message(self, message):
        """Send message to server"""
        if not self.socket:
            logger.error("Cannot send message: UDP socket not created")
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
        """Thread that receives game state updates"""
        buffer = ""

        while self.running:
            try:
                # Pour UDP, on utilise recvfrom qui retourne les données et l'adresse
                if self.socket is None:
                    logger.debug("Socket closed, exiting receive thread")
                    break

                # Définir un timeout pour permettre de vérifier self.running périodiquement
                self.socket.settimeout(0.5)

                # Vérifier si on a reçu un ping récemment
                current_time = time.time()
                if (
                    current_time - self.last_ping_time
                    > self.client.config.server_timeout_seconds
                ):
                    logger.warning(
                        f"Server hasn't sent a ping for {self.client.config.server_timeout_seconds} seconds, disconnecting"
                    )
                    # Déconnecter le client
                    self.disconnect(stop_client=True)
                    break

                # Pour UDP, on utilise recvfrom qui retourne les données et l'adresse
                data, addr = self.socket.recvfrom(4096)

                if not data:
                    continue

                # Add data to buffer
                buffer += data.decode()

                # Process complete messages
                while "\n" in buffer:
                    # Extract complete message
                    message, buffer = buffer.split("\n", 1)
                    if not message:
                        logger.debug("Empty message, skipping")
                        continue

                    try:
                        # Parse JSON message
                        message_data = json.loads(message)

                        # Check message type
                        if "type" in message_data:
                            message_type = message_data["type"]

                            # Handle different message types
                            if message_type == "state":
                                self.client.handle_state_data(message_data["data"])

                            elif message_type == "spawn_success":
                                self.client.agent.is_dead = False
                                self.client.agent.waiting_for_respawn = False

                            elif message_type == "game_started_success":
                                logger.info("Game has started")
                                self.client.in_waiting_room = False

                            elif message_type == "ping":
                                # Respond to ping with a pong
                                self.send_message({"type": "pong"})
                                # Mettre à jour le temps du dernier ping reçu
                                self.last_ping_time = time.time()

                            elif message_type == "pong":
                                # Mark that we received a response to our ping
                                self.client.ping_response_received = True

                            elif message_type == "game_status":
                                self.client.handle_game_status(message_data)

                            elif message_type == "join_success":
                                logger.debug("Received join success response")

                            elif message_type == "drop_wagon_success":
                                self.client.handle_drop_wagon_success(message_data)
                            elif message_type == "drop_wagon_failed":
                                pass

                            elif message_type == "leaderboard":
                                self.client.handle_leaderboard_data(
                                    message_data["data"]
                                )

                            elif message_type == "waiting_room":
                                self.client.handle_waiting_room_data(
                                    message_data["data"]
                                )

                            elif message_type == "name_check":
                                logger.debug(
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
                                logger.debug(
                                    f"Sciper available: {self.client.sciper_check_result}"
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
                                    logger.info(
                                        "Disconnecting from server after game over"
                                    )
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
                        else:
                            logger.debug(f"Received game state data: {message_data}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse message as JSON: {message}")
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
            except ConnectionResetError:
                # Don't log connection reset errors for UDP
                time.sleep(0.1)  # Don't break for UDP, just wait and retry
            except socket.error as e:
                if "10054" in str(e):
                    # This is a connection reset error, which is expected in UDP
                    # Don't log it to keep the console clean
                    pass
                elif "timed out" in str(e).lower():
                    # Socket timeout - check if game is over
                    if self.client.game_over:
                        logger.info("Server disconnected after game over")
                        # No need to retry if game is over
                        time.sleep(1)
                    else:
                        time.sleep(0.1)  # Wait and retry
                # else:
                #     logger.error(f"Socket error receiving UDP data: {e}")
                time.sleep(0.1)  # Don't break for UDP, just wait and retry
            except Exception as e:
                logger.error(f"Error receiving UDP data: {e}")
                time.sleep(0.1)  # Don't break for UDP, just wait and retry

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

            # Generate a unique test name using timestamp
            test_name = f"test_{int(time.time())}"

            # Send a name check request (this is allowed for unregistered clients)
            check_message = {"action": "check_name", "agent_name": test_name}
            success = self.send_message(check_message)

            if not success:
                logger.error("Failed to send name check message")
                return False

            # Wait for the name check response (which will be handled by receive_game_state thread)
            timeout = 2.0  # 2 second timeout
            start_time = time.time()

            # Wait for name check response
            while (
                not self.client.name_check_received
                and time.time() - start_time < timeout
            ):
                time.sleep(0.1)

            if not self.client.name_check_received:
                logger.error(
                    f"Timeout waiting for name check response from server at {self.host}:{self.port}"
                )
                return False

            # If we get here, we received a response
            return True

        except Exception as e:
            logger.error(f"Error verifying connection: {e}")
            return False

    def send_agent_ids(self, agent_name, agent_sciper):
        """Send agent name and sciper to server"""
        message = {
            "type": "agent_ids",
            "agent_name": agent_name,
            "agent_sciper": agent_sciper,
        }
        return self.send_message(message)

    def check_name_availability(self, name):
        """Check if a name is available on the server

        Returns True if name is available, False otherwise.
        """
        logger.info(f"Checking name availability for '{name}'")
        # Reset check variables
        self.client.name_check_received = False
        self.client.name_check_result = False

        # Send check request
        message = {"action": "check_name", "agent_name": name}
        success = self.send_message(message)

        if not success:
            logger.error(f"Failed to send name check request for '{name}'")
            return False

        # Wait for server response (with timeout)
        timeout = 5.0  # 5 second timeout
        start_time = time.time()

        logger.debug(f"Waiting for response with timeout of {timeout} seconds...")

        while (
            not self.client.name_check_received and time.time() - start_time < timeout
        ):
            time.sleep(0.1)

        if not self.client.name_check_received:
            logger.warning(f"Timeout waiting for name check response for '{name}'")
            return False

        logger.debug(f"Received name check response: {self.client.name_check_result}")
        return self.client.name_check_result

    def check_sciper_availability(self, sciper):
        """Check if a sciper is available on the server

        Returns True if sciper is available, False otherwise.
        """
        logger.info(f"Checking sciper availability for '{sciper}'")
        # Reset check variables
        self.client.sciper_check_received = False
        self.client.sciper_check_result = False

        # Send check request
        message = {"action": "check_sciper", "agent_sciper": sciper}
        success = self.send_message(message)

        if not success:
            logger.error(f"Failed to send sciper check request for '{sciper}'")
            return False

        # Wait for server response (with timeout)
        timeout = 5.0  # 5 second timeout
        start_time = time.time()

        logger.debug(f"Waiting for response with timeout of {timeout} seconds...")

        while (
            not self.client.sciper_check_received and time.time() - start_time < timeout
        ):
            time.sleep(0.1)

        if not self.client.sciper_check_received:
            logger.warning(f"Timeout waiting for sciper check response for '{sciper}'")
            return False

        logger.debug(
            f"Received sciper check response: {self.client.sciper_check_result}"
        )
        return self.client.sciper_check_result

    def send_direction_change(self, direction):
        """Send direction change to server"""
        message = {"action": "direction", "direction": direction}
        return self.send_message(message)

    def send_spawn_request(self):
        """Send spawn request to server"""
        message = {"action": "respawn"}
        return self.send_message(message)

    def send_start_game_request(self):
        """Send request to start game"""
        message = {"action": "start_game"}
        return self.send_message(message)

    def send_drop_wagon_request(self):
        """Send request to drop passenger"""
        message = {"action": "drop_wagon"}
        return self.send_message(message)
