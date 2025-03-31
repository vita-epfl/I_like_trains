"""
Module for handling events for the I Like Trains client
"""

import pygame
import logging


# Configure the logger
logger = logging.getLogger("client.event_handler")


class EventHandler:
    """Class responsible for handling client events"""

    def __init__(self, client, activate_agent, manual_control):
        """Initialize the event handler with a reference to the client"""
        self.client = client
        self.activate_agent = activate_agent
        self.manual_control = manual_control

    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.client.running = False
                return

            elif event.type == pygame.KEYDOWN:
                # If game is over, only handle ESC key to exit
                if hasattr(self.client, "game_over") and self.client.game_over:
                    if event.key == pygame.K_ESCAPE:
                        self.client.running = False
                        return
                    # Ignore all other key presses when game is over
                    continue

                # If the agent is dead and the space key is pressed, request a respawn
                if event.key == pygame.K_SPACE:
                    if (
                        self.client.agent.is_dead
                        and self.client.agent.waiting_for_respawn
                    ):
                        # Set waiting for respawn explicitly when sending request
                        result = self.client.network.send_spawn_request()
                        if result:
                            self.client.agent.waiting_for_respawn = True
                    if self.client.in_waiting_room:
                        self.client.network.send_start_game_request()

                if self.manual_control:
                    # Change the train's direction based on the pressed keys
                    if event.key == pygame.K_UP:
                        self.client.network.send_direction_change((0, -1))
                    elif event.key == pygame.K_DOWN:
                        self.client.network.send_direction_change((0, 1))
                    elif event.key == pygame.K_LEFT:
                        self.client.network.send_direction_change((-1, 0))
                    elif event.key == pygame.K_RIGHT:
                        self.client.network.send_direction_change((1, 0))
                    # key D drops a wagon
                    elif event.key == pygame.K_d:
                        self.client.network.send_drop_wagon_request()

                # Quit the game if the Escape key is pressed
                if event.key == pygame.K_ESCAPE:
                    self.client.running = False
                    return
