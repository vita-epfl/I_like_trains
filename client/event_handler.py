"""
Module for handling events for the I Like Trains client
"""

from __future__ import annotations

import pygame
import logging
from typing import TYPE_CHECKING

from common.client_config import GameMode
from common.move import Move

if TYPE_CHECKING:
    from client.client import Client


# Configure the logger
logger = logging.getLogger("client.event_handler")


class EventHandler:
    """Class responsible for handling client events"""

    def __init__(self, client: Client, game_mode: GameMode) -> None:
        """Initialize the event handler with a reference to the client"""
        self.client: Client = client
        self.game_mode: GameMode = game_mode

    def handle_events(self) -> None:
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.client.running = False
                return

            elif event.type == pygame.KEYDOWN:
                # If game is over, only handle ESC key to exit
                if self.client.game_over:
                    if event.key == pygame.K_ESCAPE:
                        self.client.running = False
                        return
                    # Ignore all other key presses when game is over
                    continue

                # If the agent is dead and the space key is pressed, request a respawn
                if event.key == pygame.K_SPACE:
                    if self.client.is_dead and self.client.waiting_for_respawn:
                        # Set waiting for respawn explicitly when sending request
                        result = self.client.network.send_spawn_request()
                        if result:
                            self.client.waiting_for_respawn = True

                if self.game_mode == GameMode.MANUAL:
                    # Change the train's direction based on the pressed keys
                    if event.key == pygame.K_UP:
                        self.client.network.send_direction_change(Move.UP.value)
                    elif event.key == pygame.K_DOWN:
                        self.client.network.send_direction_change(Move.DOWN.value)
                    elif event.key == pygame.K_LEFT:
                        self.client.network.send_direction_change(Move.LEFT.value)
                    elif event.key == pygame.K_RIGHT:
                        self.client.network.send_direction_change(Move.RIGHT.value)
                    # key D drops a wagon
                    elif event.key == pygame.K_d:
                        self.client.network.send_drop_wagon_request()

                # Quit the game if the Escape key is pressed
                if event.key == pygame.K_ESCAPE:
                    self.client.running = False
                    return
