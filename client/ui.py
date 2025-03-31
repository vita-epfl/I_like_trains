"""
Module for the user interface of the I Like Trains client
"""

import pygame
import logging


# Configure the logger
logger = logging.getLogger("client.ui")


class UI:
    """Class responsible for the client's user interface"""

    def __init__(self, client):
        """Initialize the UI with a reference to the client"""
        self.client = client

    def get_player_ids(self):
        logger.info("Requesting player name and sciper")
        """Display a screen allowing the player to enter their name and sciper"""
        if not self.client.is_initialized or self.client.screen is None:
            logger.error("Cannot show name input screen: pygame not initialized")
            return "Player", ""  # Default name and empty sciper

        # Colors
        WHITE = (255, 255, 255)
        BLACK = (0, 0, 0)
        GRAY = (200, 200, 200)
        BLUE = (0, 0, 255)
        RED = (255, 0, 0)

        # Font
        font = pygame.font.Font(None, 36)
        small_font = pygame.font.Font(None, 24)

        # Variables for input
        input_box_name = pygame.Rect(
            self.client.screen_width / 2 - 100,
            self.client.screen_height / 2 - 40,
            200,
            32,
        )
        input_box_sciper = pygame.Rect(
            self.client.screen_width / 2 - 100,
            self.client.screen_height / 2 + 40,
            200,
            32,
        )
        color_inactive = GRAY
        color_active = BLUE
        color_name = color_inactive
        color_sciper = color_inactive
        name_active = True
        sciper_active = False
        text_name = ""
        text_sciper = ""
        train_name_done = False
        sciper_done = False
        error_message = ""

        # Input loop
        while not (train_name_done and sciper_done):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.client.running = False
                    return "Player"  # Default name if closed

                if event.type == pygame.MOUSEBUTTONDOWN:
                    # Activate/deactivate input box if clicked inside/outside
                    name_active = input_box_name.collidepoint(event.pos)
                    sciper_active = input_box_sciper.collidepoint(event.pos)
                    color_name = color_active if name_active else color_inactive
                    color_sciper = color_active if sciper_active else color_inactive

                if event.type == pygame.KEYDOWN:
                    # logger.debug(f"Key pressed: {event.key}")
                    if event.key == pygame.K_RETURN:
                        # Validate name if not empty
                        if text_name:
                            # Check if name is available on the server
                            if self.client.network.check_name_availability(text_name):
                                train_name_done = True
                            else:
                                train_name_done = False
                                error_message = (
                                    f"The train name '{text_name}' is invalid"
                                )
                        else:
                            train_name_done = False
                            error_message = "Please enter a train name"

                        if text_sciper:
                            # Check if sciper is available on the server
                            if self.client.network.check_sciper_availability(
                                text_sciper
                            ):
                                sciper_done = True
                            else:
                                sciper_done = False
                                error_message = f"The sciper '{text_sciper}' is invalid"
                        else:
                            sciper_done = False
                            error_message = "Please enter a sciper"
                    elif name_active:
                        if event.key == pygame.K_TAB:
                            # Switch to sciper field
                            name_active = False
                            sciper_active = True
                            color_name = color_inactive
                            color_sciper = color_active
                        elif event.key == pygame.K_BACKSPACE:
                            text_name = text_name[:-1]
                            error_message = ""
                        else:
                            # Limit name length
                            if len(text_name) < 10:
                                text_name += event.unicode
                                error_message = ""
                    elif sciper_active:
                        if event.key == pygame.K_TAB:
                            # Switch to name field
                            name_active = True
                            sciper_active = False
                            color_name = color_active
                            color_sciper = color_inactive
                        elif event.key == pygame.K_BACKSPACE:
                            text_sciper = text_sciper[:-1]
                            error_message = ""
                        else:
                            # Limit sciper length
                            if len(text_sciper) < 10:
                                text_sciper += event.unicode
                                error_message = ""

            # Draw screen
            self.client.screen.fill(WHITE)

            # Title
            title = font.render("Enter your train name and sciper", True, BLACK)
            title_rect = title.get_rect(
                center=(
                    self.client.screen_width / 2,
                    self.client.screen_height / 2 - 100,
                )
            )
            self.client.screen.blit(title, title_rect)

            # Label for name
            name_label = small_font.render("Name:", True, BLACK)
            name_label_rect = name_label.get_rect(
                topleft=(input_box_name.x, input_box_name.y - 25)
            )
            self.client.screen.blit(name_label, name_label_rect)

            # Input box for name
            pygame.draw.rect(self.client.screen, color_name, input_box_name, 2)
            text_surface = font.render(text_name, True, BLACK)
            width = max(200, text_surface.get_width() + 10)
            input_box_name.w = width
            input_box_name.x = self.client.screen_width / 2 - width / 2
            self.client.screen.blit(
                text_surface, (input_box_name.x + 5, input_box_name.y + 5)
            )

            # Label for sciper
            sciper_label = small_font.render("Sciper:", True, BLACK)
            sciper_label_rect = sciper_label.get_rect(
                topleft=(input_box_sciper.x, input_box_sciper.y - 25)
            )
            self.client.screen.blit(sciper_label, sciper_label_rect)

            # Input box for sciper
            pygame.draw.rect(self.client.screen, color_sciper, input_box_sciper, 2)
            text_surface = font.render(text_sciper, True, BLACK)
            width = max(200, text_surface.get_width() + 10)
            input_box_sciper.w = width
            input_box_sciper.x = self.client.screen_width / 2 - width / 2
            self.client.screen.blit(
                text_surface, (input_box_sciper.x + 5, input_box_sciper.y + 5)
            )

            # Error message
            if error_message:
                error_surface = small_font.render(error_message, True, RED)
                error_rect = error_surface.get_rect(
                    center=(
                        self.client.screen_width / 2,
                        self.client.screen_height / 2 + 120,
                    )
                )
                self.client.screen.blit(error_surface, error_rect)

            # Instructions
            instructions = small_font.render("Press Enter to validate", True, BLACK)
            instructions_rect = instructions.get_rect(
                center=(
                    self.client.screen_width / 2,
                    self.client.screen_height / 2 + 100,
                )
            )
            self.client.screen.blit(instructions, instructions_rect)

            pygame.display.flip()

        return text_name, text_sciper
