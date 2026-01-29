"""
Graphics rendering module for the I Like Trains client
"""

from __future__ import annotations

import pygame
import logging
import time
from typing import TYPE_CHECKING

from common.move import Move

if TYPE_CHECKING:
    from client.client import Client

# Configure logger
logger = logging.getLogger("client.renderer")
logger.setLevel(logging.DEBUG)


class Renderer:
    """Class responsible for rendering the game"""

    def __init__(self, client: Client) -> None:
        """Initialize renderer with a reference to the client"""
        self.client: Client = client
        self.sorted_trains: list[tuple[str, int, int]] = []
        self.leaderboard_dirty: bool = True
        self.last_scores_hash: int = 0
        self.leaderboard_update_counter: int = 0
        self.max_leaderboard_entries: int = 15
        
        # Text rendering cache to avoid expensive font.render() calls
        self.text_cache: dict[tuple, pygame.Surface] = {}
        self.font_cache: dict[tuple, pygame.font.Font] = {}

    def draw_game(self) -> None:
        """Draws the game."""
        # Check if screen is available
        if not self.client.is_initialized or self.client.screen is None:
            logger.error("Cannot draw game: pygame not initialized or screen is None")
            return

        self.client.profiler.start_timer("render_total")
        
        # Fill screen with background color (white)
        self.client.screen.fill((255, 255, 255))

        # If in waiting room, display waiting screen
        if self.client.in_waiting_room:
            self.draw_waiting_room()
            # Update display
            pygame.display.flip()
            return

        # If game is over, display game over screen
        if self.client.game_over:
            self.draw_game_over_screen()
            # Update display
            pygame.display.flip()
            return

        # Draw a light grid across the full game area
        grid_color = (230, 230, 230)  # Very light gray
        outline_color = (200, 200, 200)  # Slightly darker gray for outlines
        outline_width = 3  # Thicker width for outlines

        # Draw inner grid lines only if cell_size is not zero
        if self.client.cell_size > 0:
            for x in range(
                self.client.game_screen_padding,
                self.client.game_width + self.client.game_screen_padding,
                self.client.cell_size,
            ):
                pygame.draw.line(
                    self.client.screen,
                    grid_color,
                    (x, self.client.game_screen_padding),
                    (
                        x,
                        self.client.game_height
                        + self.client.game_screen_padding,
                    ),
                    1,
                )
            for y in range(
                self.client.game_screen_padding,
                self.client.game_height + self.client.game_screen_padding,
                self.client.cell_size,
            ):
                pygame.draw.line(
                    self.client.screen,
                    grid_color,
                    (self.client.game_screen_padding, y),
                    (
                        self.client.game_width
                        + self.client.game_screen_padding,
                        y,
                    ),
                    1,
                )

        # Draw outer border with thicker lines
        pygame.draw.rect(
            self.client.screen,
            outline_color,
            (
                self.client.game_screen_padding - outline_width,
                self.client.game_screen_padding - outline_width,
                self.client.game_width + 2 * outline_width,
                self.client.game_height + 2 * outline_width,
            ),
            outline_width,
        )

        self.client.profiler.start_timer("render_delivery_zone")
        self.draw_delivery_zone()
        self.client.profiler.end_timer("render_delivery_zone")

        self.client.profiler.start_timer("render_passengers")
        self.draw_passengers()
        self.client.profiler.end_timer("render_passengers")

        self.client.profiler.start_timer("render_trains")
        self.draw_trains()
        self.client.profiler.end_timer("render_trains")

        self.client.profiler.start_timer("render_leaderboard")
        self.leaderboard_update_counter += 1
        self.draw_leaderboard()
        self.client.profiler.end_timer("render_leaderboard")

        if self.client.is_dead and not self.client.in_waiting_room:
            self.draw_death_screen()

        # Update display
        self.client.profiler.start_timer("display_flip")
        pygame.display.flip()
        self.client.profiler.end_timer("display_flip")
        
        self.client.profiler.end_timer("render_total")

    def draw_delivery_zone(self) -> None:
        # Draw delivery zone
        delivery_zone = self.client.delivery_zone
        if delivery_zone:
            x, y = delivery_zone["position"]
            x += self.client.game_screen_padding
            y += self.client.game_screen_padding

            # Create a surface with per-pixel alpha
            s = pygame.Surface(
                (delivery_zone["width"], delivery_zone["height"]), pygame.SRCALPHA
            )
            # Fill with semi-transparent red (fourth parameter is alpha, 128 = semi-transparent)
            s.fill((255, 0, 0, 128))
            # Blit the surface onto the screen
            self.client.screen.blit(s, (x, y))

    def draw_passengers(self) -> None:
        """
        Draw passengers and their values
        """
        for passenger in self.client.passengers:
            if isinstance(passenger, dict):
                if "position" in passenger:
                    x, y = passenger["position"]
                    x += self.client.game_screen_padding
                    y += self.client.game_screen_padding
                    value = passenger.get("value", 1)
                else:
                    logger.warning(
                        "Passenger dict without position: " + str(passenger)
                    )
                    continue
            else:
                logger.warning("Unrecognized passenger format: " + str(passenger))
                continue

            # Calculate color intensity based on value (1-10)
            # Higher value = more intense red
            red_intensity = max(
                100, min(255, 100 + (155 * value / 10))
            )  # Range from 100-255

            # Draw a circle to represent passengers
            pygame.draw.circle(
                self.client.screen,
                (red_intensity, 0, 0),  # Red with varying intensity
                (
                    x + self.client.cell_size // 2,
                    y + self.client.cell_size // 2,
                ),  # Circle center
                self.client.cell_size // 2 - 2,  # Circle radius slightly smaller
            )

            # Draw the value text above the passenger
            font = pygame.font.Font(None, 24)  # Default pygame font, size 24
            text = font.render(str(value), True, (0, 0, 0))  # Black text
            text_rect = text.get_rect(
                center=(x + self.client.cell_size // 2, y - 5)
            )  # Position above passenger
            self.client.screen.blit(text, text_rect)

    def draw_trains(self) -> None:
        """
        Draw trains and their wagons
        """
        for nickname, train_data in self.client.trains.items():
            # Only draw if train is alive
            if isinstance(train_data, dict) and not train_data.get("alive", True):
                continue

            # Check if train data is in new format (dictionary)
            train_position = train_data.get("position", (0, 0))
            train_x, train_y = train_position
            train_x += self.client.game_screen_padding
            train_y += self.client.game_screen_padding
            train_wagons = train_data.get("wagons", [])
            train_direction = train_data.get("direction", Move.RIGHT)
            train_color = train_data.get("color", (0, 255, 0))
            train_wagon_color = tuple(
                min(c + 50, 255) for c in train_color
            )  # Wagons lighter

            # Draw main train
            color = train_color
            if nickname == self.client.nickname:
                color = (0, 0, 255)  # Blue for player's train

            # Draw train with more elaborate shape
            pygame.draw.rect(
                self.client.screen,
                color,
                pygame.Rect(
                    train_x + 1,
                    train_y + 1,
                    self.client.cell_size - 2,
                    self.client.cell_size - 2,
                ),
            )

            # Add train details (like "eyes")
            if train_direction[0] == 1:  # Right
                eye_x = train_x + 3 * self.client.cell_size // 4
                eye_y = train_y + self.client.cell_size // 4
            elif train_direction[0] == -1:  # Left
                eye_x = train_x + self.client.cell_size // 4
                eye_y = train_y + self.client.cell_size // 4
            elif train_direction[1] == 1:  # Down
                eye_x = train_x + self.client.cell_size // 4
                eye_y = train_y + 3 * self.client.cell_size // 4
            else:  # Up
                eye_x = train_x + self.client.cell_size // 4
                eye_y = train_y + self.client.cell_size // 4

            # Draw train's "eyes"
            pygame.draw.circle(
                self.client.screen,
                (255, 255, 255),  # White
                (eye_x, eye_y),
                self.client.cell_size // 8,
            )

            # Draw wagons
            for wagon_pos in train_wagons:
                wagon_x, wagon_y = wagon_pos
                wagon_x += self.client.game_screen_padding
                wagon_y += self.client.game_screen_padding
                wagon_color = train_wagon_color
                if nickname == self.client.nickname:
                    wagon_color = (50, 50, 200)  # Darker blue for player's wagons

                pygame.draw.rect(
                    self.client.screen,
                    wagon_color,
                    pygame.Rect(
                        wagon_x + 2,
                        wagon_y + 2,
                        self.client.cell_size - 4,
                        self.client.cell_size - 4,
                    ),
                )

    def draw_waiting_room(self) -> None:
        """Display the waiting room screen"""
        # Check if screen is available
        if not self.client.is_initialized or self.client.screen is None:
            logger.error(
                "Cannot draw waiting room: pygame not initialized or screen is None"
            )
            return

        # Fill screen with background color
        self.client.screen.fill((240, 240, 255))  # Very light blue

        # Waiting room title
        font_title = pygame.font.Font(None, 48)
        title = font_title.render("Waiting for players...", True, (0, 0, 100))
        rect_size = title.get_size()
        title_rect = title.get_rect(
            center=(rect_size[0] // 2 + 20, rect_size[1] // 2 + 20)
        )
        self.client.screen.blit(title, title_rect)

        # Display waiting room information if available
        if self.client.waiting_room_data and self.client.in_waiting_room:
            # Display players in room
            font = pygame.font.Font(None, 32)
            players = self.client.waiting_room_data.get("players", [])

            # Display player count and maximum
            nb_players = self.client.waiting_room_data.get("nb_players", 0)
            players_count = len(players)
            count_text = font.render(
                "Players: " + str(players_count) + "/" + str(nb_players),
                True,
                (0, 0, 100),
            )
            self.client.screen.blit(count_text, (50, 80))

            # Display waiting time if available
            waiting_time = self.client.waiting_room_data.get("waiting_time", None)
            if waiting_time is not None and waiting_time > 0:
                time_text = font.render(
                    f"Starting in: {waiting_time} seconds",
                    True,
                    (200, 0, 0),  # Red color for emphasis
                )
                self.client.screen.blit(time_text, (50, 110))
            elif (
                waiting_time is not None
                and waiting_time == 0
                and players_count < nb_players
            ):
                time_text = font.render(
                    "Adding bots and starting game...",
                    True,
                    (200, 0, 0),  # Red color for emphasis
                )
                self.client.screen.blit(time_text, (50, 110))

            # Player list title
            players_title = font.render("Players:", True, (0, 0, 100))
            self.client.screen.blit(
                players_title, (50, 150)
            )  # Moved down to make room for waiting time

            # Column configuration
            column_width = 240
            players_per_column = 10
            start_y = 190  # Moved down to make room for waiting time

            # List players in multiple columns
            for i, player in enumerate(players):
                column = i // players_per_column
                row = i % players_per_column
                x = 20 + (column * column_width)
                y = start_y + (row * 40)

                player_text = font.render(
                    str(i + 1) + ". " + str(player), True, (0, 0, 0)
                )
                self.client.screen.blit(player_text, (x, y))
        else:
            font = pygame.font.Font(None, 32)
            message = font.render("Waiting for server data...", True, (0, 0, 100))
            message_rect = message.get_rect(
                center=(
                    self.client.screen_width // 2,
                    self.client.screen_height // 2,
                )
            )
            self.client.screen.blit(message, message_rect)

        # Update display
        pygame.display.flip()

    def draw_death_screen(self) -> None:
        # If agent is dead, display respawn message with cooldown

        elapsed = time.time() - self.client.death_time
        remaining_time = max(0, self.client.respawn_cooldown - elapsed)

        if remaining_time > 0:
            # Display cooldown
            font = pygame.font.Font(None, 28)
            text = font.render(
                "Respawn in " + str(int(remaining_time) + 1) + " seconds",
                True,
                (255, 0, 0),
            )
            text_rect = text.get_rect(
                center=(
                    self.client.game_screen_padding + self.client.game_width // 2,
                    self.client.game_height / 2 + self.client.game_screen_padding,
                )
            )
            self.client.screen.blit(text, text_rect)

        elif self.client.waiting_for_respawn and self.client.config.manual_spawn:
            # Display respawn message in center of screen
            font = pygame.font.Font(None, 28)
            text = font.render("Press SPACE to spawn", True, (0, 200, 0))
            text_rect = text.get_rect(
                center=(
                    self.client.game_screen_padding + self.client.game_width // 2,
                    self.client.game_height / 2 + self.client.game_screen_padding,
                )
            )
            self.client.screen.blit(text, text_rect)

    def get_cached_text(self, text: str, font_size: int, color: tuple, bold: bool = False) -> pygame.Surface:
        """Get cached rendered text surface to avoid expensive font.render() calls"""
        # Convert color to tuple if it's a list (for hashability)
        if isinstance(color, list):
            color = tuple(color)
        
        cache_key = (text, font_size, color, bold)
        
        if cache_key not in self.text_cache:
            font_key = (font_size, bold)
            if font_key not in self.font_cache:
                self.font_cache[font_key] = pygame.font.Font(None, font_size)
            
            font = self.font_cache[font_key]
            self.text_cache[cache_key] = font.render(text, True, color)
        
        return self.text_cache[cache_key]

    def draw_leaderboard(self) -> None:
        """Draw the leaderboard with train scores"""
        # Define leaderboard area
        leaderboard_rect = pygame.Rect(
            self.client.game_width + 2 * self.client.game_screen_padding,
            0,
            self.client.leaderboard_width,
            self.client.screen_height,
        )

        # Draw leaderboard background
        pygame.draw.rect(self.client.screen, (240, 240, 240), leaderboard_rect)

        # Draw a line to separate leaderboard from game area
        pygame.draw.line(
            self.client.screen,
            (100, 100, 100),
            (self.client.game_width + 2 * self.client.game_screen_padding, 0),
            (
                self.client.game_width + 2 * self.client.game_screen_padding,
                self.client.screen_height,
            ),
            2,
        )

        # Add a title with colored background
        title_rect = pygame.Rect(
            self.client.game_width + 2 * self.client.game_screen_padding,
            0,
            self.client.leaderboard_width,
            40,
        )
        pygame.draw.rect(self.client.screen, (50, 50, 150), title_rect)

        title = self.get_cached_text("LEADERBOARD", 28, (255, 255, 255))
        title_rect = title.get_rect(
            center=(
                self.client.game_width
                + self.client.leaderboard_width // 2
                + 2 * self.client.game_screen_padding,
                20,
            )
        )
        self.client.screen.blit(title, title_rect)

        # Add a header
        header_y = 50

        # Draw columns with distinct titles (using cached text)
        rank_header = self.get_cached_text("Rank", 24, (0, 0, 100))
        self.client.screen.blit(
            rank_header,
            (
                self.client.game_width + 2 * self.client.game_screen_padding + 10,
                header_y,
            ),
        )

        player_header = self.get_cached_text("Player", 24, (0, 0, 100))
        self.client.screen.blit(
            player_header,
            (
                self.client.game_width + 2 * self.client.game_screen_padding + 70,
                header_y,
            ),
        )

        score_header = self.get_cached_text("Score", 24, (0, 0, 100))
        self.client.screen.blit(
            score_header,
            (
                self.client.game_width + 2 * self.client.game_screen_padding + 170,
                header_y,
            ),
        )

        best_score_header = self.get_cached_text("Best", 24, (0, 0, 100))
        self.client.screen.blit(
            best_score_header,
            (
                self.client.game_width + 2 * self.client.game_screen_padding + 230,
                header_y,
            ),
        )

        # Add a line to separate header from player list
        pygame.draw.line(
            self.client.screen,
            (200, 200, 200),
            (
                self.client.game_width + 2 * self.client.game_screen_padding + 5,
                header_y + 20,
            ),
            (
                self.client.game_width
                + 2 * self.client.game_screen_padding
                + self.client.leaderboard_width
                - 5,
                header_y + 20,
            ),
            2,
        )

        # Only update sorted trains if scores have changed, train count changed, or every 10 frames
        # This reduces expensive sorting operations from 60/sec to 6/sec
        current_scores_hash = hash(tuple(sorted(self.client.best_scores.items())))
        should_update = (
            self.leaderboard_dirty or 
            current_scores_hash != self.last_scores_hash or 
            len(self.sorted_trains) != len(self.client.trains) or
            self.leaderboard_update_counter % 10 == 0
        )
        
        if should_update:
            
            # Get train data for leaderboard
            self.sorted_trains = [(
                    nickname,
                    self.client.best_scores.get(nickname, 0),
                    train_data.get("score", 0),
                ) for nickname, train_data in self.client.trains.items()]

            # Sort by best score in descending order
            self.sorted_trains.sort(key=lambda x: x[1], reverse=True)
            
            self.last_scores_hash = current_scores_hash
            self.leaderboard_dirty = False

        # Display players in leaderboard
        y_offset = header_y + 30

        # Limit to top N entries for performance
        visible_entries = self.sorted_trains[:self.max_leaderboard_entries]
        
        for i, (nickname, best_score, current_score) in enumerate(visible_entries):

            # Determine color based on rank
            if i == 0:
                rank_color = (218, 165, 32)  # Gold
            elif i == 1:
                rank_color = (192, 192, 192)  # Silver
            elif i == 2:
                rank_color = (205, 127, 50)  # Bronze
            else:
                rank_color = (100, 100, 100)  # Gray

            # Highlight current player's row
            if self.client.agent:
                if nickname == self.client.nickname:
                    pygame.draw.rect(
                        self.client.screen,
                        (220, 220, 255),  # Light blue background
                        pygame.Rect(
                            self.client.game_width
                            + 2 * self.client.game_screen_padding
                            + 5,
                            y_offset - 2,
                            self.client.leaderboard_width - 10,
                            20,
                        ),
                    )

            # Get train color
            train_color = (0, 0, 0)  # Default color
            if nickname in self.client.trains:
                train_data = self.client.trains[nickname]
                if isinstance(train_data, dict) and "color" in train_data:
                    train_color = train_data["color"]
                if self.client.agent:
                    if nickname == self.client.nickname:
                        train_color = (0, 0, 255)  # Blue for player's train

            # Display rank (cached)
            rank_text = self.get_cached_text(str(i + 1), 22, rank_color)
            self.client.screen.blit(
                rank_text,
                (
                    self.client.game_width
                    + 2 * self.client.game_screen_padding
                    + 30,
                    y_offset,
                ),
            )

            # Display player name with train color (cached)
            name_text = self.get_cached_text(nickname[:15], 22, train_color)
            self.client.screen.blit(
                name_text,
                (
                    self.client.game_width
                    + 2 * self.client.game_screen_padding
                    + 60,
                    y_offset,
                ),
            )

            # Display current score (cached)
            score_text = self.get_cached_text(str(current_score), 22, (0, 0, 0))
            self.client.screen.blit(
                score_text,
                (
                    self.client.game_width
                    + 2 * self.client.game_screen_padding
                    + 185,
                    y_offset,
                ),
            )

            # Display best score (cached)
            best_score_text = self.get_cached_text(str(best_score), 22, (0, 0, 0))
            self.client.screen.blit(
                best_score_text,
                (
                    self.client.game_width
                    + 2 * self.client.game_screen_padding
                    + 240,
                    y_offset,
                ),
            )

            y_offset += 25

        # Show indicator if there are more players not displayed
        if len(self.sorted_trains) > self.max_leaderboard_entries:
            hidden_count = len(self.sorted_trains) - self.max_leaderboard_entries
            more_text = self.get_cached_text(
                f"... and {hidden_count} more players",
                22,
                (100, 100, 100)
            )
            self.client.screen.blit(
                more_text,
                (
                    self.client.game_width + 2 * self.client.game_screen_padding + 60,
                    y_offset,
                ),
            )
            y_offset += 30

        # Draw remaining time below the leaderboard
        if hasattr(self.client, "remaining_game_time"):
            # Format time as mm:ss
            remaining = self.client.remaining_game_time
            minutes = int(remaining) // 60
            seconds = int(remaining) % 60
            time_text = f"Time remaining: {minutes:02d}:{seconds:02d}"

            # Draw time with a background
            time_rect = pygame.Rect(
                self.client.game_width + 2 * self.client.game_screen_padding + 5,
                y_offset + 10,
                self.client.leaderboard_width - 10,
                30,
            )
            pygame.draw.rect(self.client.screen, (50, 50, 150), time_rect)

            # Draw time text
            time_font = pygame.font.Font(None, 24)
            time_surface = time_font.render(time_text, True, (255, 255, 255))
            time_text_rect = time_surface.get_rect(
                center=(
                    self.client.game_width
                    + 2 * self.client.game_screen_padding
                    + self.client.leaderboard_width // 2,
                    y_offset + 25,
                )
            )
            self.client.screen.blit(time_surface, time_text_rect)

    def draw_game_over_screen(self) -> None:
        """Display the game over screen with final scores"""
        # Fill screen with a dark background
        overlay = pygame.Surface(
            (self.client.screen_width, self.client.screen_height)
        )
        overlay.fill((240, 240, 255))  # Dark blue background
        self.client.screen.blit(overlay, (0, 0))

        # Draw message
        font_message = pygame.font.Font(None, 36)
        if self.client.game_over_data:
            message = self.client.game_over_data.get(
                "message", "Time limit reached."
            )
        else:
            message = "Time limit reached."
        message_text = font_message.render(message, True, (0, 0, 0))
        message_rect = message_text.get_rect(
            center=(self.client.screen_width // 2, 70)
        )
        self.client.screen.blit(message_text, message_rect)

        # Draw final scores title
        font_scores_title = pygame.font.Font(None, 48)
        scores_title = font_scores_title.render("Final Scores", True, (0, 0, 0))
        scores_title_rect = scores_title.get_rect(
            center=(self.client.screen_width // 2, 120)
        )
        self.client.screen.blit(scores_title, scores_title_rect)

        # Draw scores table
        font_scores = pygame.font.Font(None, 32)
        y_offset = 170

        # Draw table headers
        header_rank = font_scores.render("Rank", True, (0, 0, 0))
        header_name = font_scores.render("Player", True, (0, 0, 0))
        header_score = font_scores.render("Best scores", True, (0, 0, 0))

        # Calculate positions for centered table
        table_width = 400
        col1_x = self.client.screen_width // 2 - table_width // 2 + 50
        col2_x = self.client.screen_width // 2 - 50
        col3_x = self.client.screen_width // 2 + table_width // 2 - 130

        self.client.screen.blit(header_rank, (col1_x, y_offset))
        self.client.screen.blit(header_name, (col2_x, y_offset))
        self.client.screen.blit(header_score, (col3_x + 50, y_offset))

        y_offset += 30

        # Draw horizontal line
        pygame.draw.line(
            self.client.screen,
            (200, 200, 200),
            (col1_x - 30, y_offset),
            (col3_x + 130, y_offset),
            2,
        )

        y_offset += 20

        # Get scores to display
        scores_to_display = []
        if self.client.final_scores:
            # Use final scores from game over data
            for score_data in self.client.final_scores:
                name = score_data.get("name", "Unknown")
                best_score = score_data.get("best_score", 0)
                scores_to_display.append((name, best_score))
        else:
            # Use current leaderboard data
            for name, best_score, _ in self.sorted_trains:
                scores_to_display.append((name, best_score))

        # Sort scores in descending order
        scores_to_display.sort(key=lambda x: x[1], reverse=True)

        # Draw scores
        for i, (player_name, player_score) in enumerate(scores_to_display):
            # Limit to top 10 players
            if i >= 10:
                break

            # Determine color based on rank
            if i == 0:
                rank_color = (255, 215, 0)  # Gold
            elif i == 1:
                rank_color = (192, 192, 192)  # Silver
            elif i == 2:
                rank_color = (205, 127, 50)  # Bronze
            else:
                rank_color = (255, 255, 255)  # White

            # Highlight current player
            if self.client.agent:
                if player_name == self.client.nickname:
                    # Draw highlight rectangle
                    pygame.draw.rect(
                        self.client.screen,
                        (0, 0, 100),  # Blue
                        pygame.Rect(
                            col1_x - 30,
                            y_offset - 10,
                            col3_x - col1_x + 160,
                            40,
                        ),
                        border_radius=5,
                    )
                    rank_color = (255, 255, 255)

            # Draw rank
            rank_text = font_scores.render(f"#{i + 1}", True, rank_color)
            self.client.screen.blit(rank_text, (col1_x, y_offset))

            # Draw name
            name_text = font_scores.render(player_name, True, rank_color)
            self.client.screen.blit(name_text, (col2_x, y_offset))

            # Draw score
            score_text = font_scores.render(str(player_score), True, rank_color)
            self.client.screen.blit(score_text, (col3_x + 100, y_offset))

            y_offset += 40

        # Draw message to exit
        font_exit = pygame.font.Font(None, 28)
        exit_text = font_exit.render("Press ESC to exit", True, (200, 200, 200))
        exit_rect = exit_text.get_rect(
            center=(self.client.screen_width // 2, y_offset + 50)
        )
        self.client.screen.blit(exit_text, exit_rect)
