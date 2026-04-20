import asyncio
import datetime
import logging
import math
from enum import Enum

import pygame

from common.base_agent import KeyEvent
from common.config import ClientConfig
from common.state import GameState, Passenger, RoomState, Slot

# Configure logger
logger = logging.getLogger("client.renderer")
logger.setLevel(logging.DEBUG)

DESTINATION_COLORS = {
    "A": pygame.Color("#8FA3BF"),  # muted steel blue
    "B": pygame.Color("#A3BE8C"),  # soft moss green
    "C": pygame.Color("#B48EAD"),  # dusty lavender
    "D": pygame.Color("#D08770"),  # subdued terracotta
}
OTHER_DESTINATION_COLOR = pygame.Color("#FF0000")

SLOT_COLORS = [
    pygame.Color("#1B998B"),  # deep teal
    pygame.Color("#2E5BFF"),  # bold royal blue
    pygame.Color("#FF6F00"),  # bright orange
    pygame.Color("#6A0DAD"),  # rich purple
    pygame.Color("#008B45"),  # strong green
    pygame.Color("#C2185B"),  # deep pink
    pygame.Color("#0057B7"),  # saturated blue
    pygame.Color("#B22222"),  # firebrick red
    pygame.Color("#3A7D44"),  # earthy green
    pygame.Color("#7B1FA2"),  # vibrant violet
    pygame.Color("#0F4C81"),  # dark azure blue
    pygame.Color("#E65100"),  # burnt orange
    pygame.Color("#4A148C"),  # deep indigo purple
    pygame.Color("#006064"),  # dark cyan teal
    pygame.Color("#9C27B0"),  # bright amethyst purple
    pygame.Color("#2C3E50"),  # charcoal blue-gray
    pygame.Color("#D7263D"),  # vivid crimson red
]

BACKGROUND_COLOR = pygame.Color("white")
TEXT_COLOR = pygame.Color("black")
GRASS_COLOR = pygame.Color("#0B640B")  # dark green
OUR_COLOR = pygame.Color("#FF0000")
ROAD_COLOR = pygame.Color("#D4D4D4")  # dark gray
STAFF_BADGE_COLOR = pygame.Color("#a8930b")  # gold


class ConnectionState(Enum):
    CONNECTING = "Connecting..."
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected!"


# Note:
# if rendering becomes an issue, we can cache more rendering:
# - either cache the score title surface
# - or cache the entire score table
# - cache the passengers circle. The cache would need to be per passenger value + destination color
#   and needs to be discarded if the window is resized (cell size changes)


class Renderer:
    """
    Contains all the UI-related code
    """

    def __init__(self, config: ClientConfig) -> None:
        pygame.init()
        self.config = config
        self.slot: Slot | None = None
        self.connection_state = ConnectionState.CONNECTING
        self.room_state: RoomState | None = None
        self.game_state: GameState | None = None
        self.key_event: KeyEvent | None = None
        self.window = pygame.Window(
            "I ❤️ Buses",
            (self.config.window_width, self.config.window_height),
            allow_high_dpi=True,
            resizable=True,
        )

        # in high DPI, we need to increase the font size
        font_scale = self.window.get_surface().height / self.window.size[1]
        font_scale = max(font_scale, 1)
        self.font = pygame.font.Font(
            None, math.floor(self.config.font_size * font_scale)
        )
        self.large_font = pygame.font.Font(
            None, math.floor(self.config.font_size * font_scale * 1.5)
        )
        self.large_font.underline = True
        self.padding = self.config.ui_size * 10

        # Cache to optimize rendering
        self.background: pygame.Surface | None = None

    def update_room_state(self, slot: Slot, room_state: RoomState):
        self.slot = slot
        self.room_state = room_state

    def update_game_state(self, game_state: GameState):
        self.game_state = game_state

    async def run_event_loop(self) -> None:
        clock = pygame.Clock()
        previous_loop_ticks: None | int = None
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    exit(0)
                if self.key_event is not None:
                    if event.type == pygame.KEYDOWN:
                        self.key_event.key = pygame.key.name(event.key)
                        self.key_event.set()
                    elif event.type == pygame.KEYUP:
                        self.key_event.key = ""
            try:
                self.draw()
            except Exception as e:
                # Don't crash the client if we fail to properly draw
                # things. Things might resolve by themselves in the next
                # tick.
                logger.exception(e)

            # Give as much time as possible to asyncio.sleep so other
            # tasks (such as the network and agent) can run.
            fps = 60
            ticks = pygame.time.get_ticks()
            if previous_loop_ticks is not None:
                time_slice_ms = 1 / fps * 1000
                time_slice_ms -= ticks - previous_loop_ticks
                time_slice_ms = max(time_slice_ms, 0)
                await asyncio.sleep(time_slice_ms / 1000)
            previous_loop_ticks = ticks
            clock.tick(fps)

    def get_color(self, slot: int) -> pygame.Color:
        if self.slot == slot:
            return OUR_COLOR
        return SLOT_COLORS[slot % len(SLOT_COLORS)]

    def draw(self):
        ui_size = self.config.ui_size
        try:
            # Clear the window
            surface = self.window.get_surface()
            pygame.draw.rect(
                surface, BACKGROUND_COLOR, (0, 0, surface.width, surface.height)
            )

            footer_height = self.draw_footer(surface)
            if self.room_state is None:
                # We don't yet have a room, there's not much we more can can render
                return

            scores = self.draw_scores()

            # Calculate how much space we have to render the playing field. Find x such that:
            # - x * self.room_state.map.width + leaderboard_width <= surface.width
            # - x * self.room_state.map.height + footer_height <= surface.height
            x1 = (surface.height - footer_height) / self.room_state.map.height
            x2 = (surface.width - scores.width) / self.room_state.map.width
            cell_size = math.floor(min(x1, x2))
            if cell_size <= 0:
                # we don't have enough space to draw the game
                return
            map_height = self.room_state.map.height * cell_size
            map_width = self.room_state.map.width * cell_size
            pygame.draw.rect(
                surface, TEXT_COLOR, (0, 0, map_width, map_height), ui_size
            )
            surface.blit(
                scores,
                (
                    map_width
                    + math.floor((surface.width - map_width - scores.width) / 2),
                    0,
                ),
            )

            if self.game_state is None:
                text = self.font.render(
                    "waiting for others to join...", True, TEXT_COLOR
                )
                textpos = text.get_rect(
                    centerx=math.floor(map_width / 2),
                    centery=math.floor(map_height / 2),
                )
                surface.blit(text, textpos)
                return

            if (
                self.background is None
                or self.background.height != map_height
                or self.background.width != map_width
            ):
                # Render the map once to save some render time
                self.background = pygame.Surface((map_width, map_height))
                pygame.draw.rect(
                    self.background, GRASS_COLOR, (0, 0, map_width, map_height)
                )
                for i in range(self.room_state.map.width):
                    for j in range(self.room_state.map.height):
                        if (i, j) in self.room_state.map.available_cells:
                            pygame.draw.rect(
                                self.background,
                                ROAD_COLOR,
                                (i * cell_size, j * cell_size, cell_size, cell_size),
                            )
                        if (i, j) in self.room_state.map.delivery_zones:
                            d = self.room_state.map.delivery_zones[(i, j)]
                            c = DESTINATION_COLORS.get(d, OTHER_DESTINATION_COLOR)
                            pygame.draw.rect(
                                self.background,
                                c,
                                (
                                    i * cell_size + ui_size,
                                    j * cell_size + ui_size,
                                    cell_size - 2 * ui_size,
                                    cell_size - 2 * ui_size,
                                ),
                                2 * ui_size,
                            )

            # Draw the part which doesn't change
            surface.blit(self.background)

            # Draw passengers
            for pos, passenger in self.game_state.passengers.items():
                x, y = pos
                self.draw_passenger(
                    surface,
                    math.floor((x + 0.5) * cell_size),
                    math.floor((y + 0.5) * cell_size),
                    cell_size,
                    ui_size,
                    passenger,
                )

            # draw buses
            for slot, bus in self.game_state.buses.items():
                c = self.get_color(slot)
                if len(bus.positions) > 0:
                    x, y = bus.positions[0]
                    pygame.draw.circle(
                        surface,
                        c,
                        ((x + 0.5) * cell_size, (y + 0.5) * cell_size),
                        int(cell_size / 2) - ui_size,
                    )
                for i in range(1, len(bus.positions)):
                    x1, y1 = bus.positions[i]
                    pygame.draw.rect(
                        surface,
                        c,
                        (
                            x1 * cell_size + ui_size,
                            y1 * cell_size + ui_size,
                            cell_size - 2 * ui_size,
                            cell_size - 2 * ui_size,
                        ),
                    )

                    x2, y2 = bus.positions[i - 1]
                    if x1 == x2:
                        y3 = min(y1, y2)
                        pygame.draw.rect(
                            surface,
                            c,
                            (
                                (x1 + 0.5) * cell_size - 2 * ui_size,
                                (y3 + 0.5) * cell_size,
                                4 * ui_size,
                                cell_size,
                            ),
                        )
                    if y1 == y2:
                        x3 = min(x1, x2)
                        pygame.draw.rect(
                            surface,
                            c,
                            (
                                (x3 + 0.5) * cell_size,
                                (y1 + 0.5) * cell_size - 2 * ui_size,
                                cell_size,
                                4 * ui_size,
                            ),
                        )

            # Draw our passengers
            assert self.slot is not None
            x = surface.width - self.padding - cell_size / 2
            y = surface.height - footer_height - self.padding - cell_size / 2
            for passenger in self.game_state.buses[self.slot].passengers:
                c = DESTINATION_COLORS.get(
                    passenger.destination, OTHER_DESTINATION_COLOR
                )
                self.draw_passenger(
                    surface, math.floor(x), math.floor(y), cell_size, ui_size, passenger
                )
                x -= cell_size + self.padding

        finally:
            self.window.flip()

    def draw_passenger(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        cell_size: int,
        ui_size: int,
        passenger: Passenger,
    ) -> None:
        c = DESTINATION_COLORS.get(passenger.destination, OTHER_DESTINATION_COLOR)
        pygame.draw.circle(
            surface,
            c,
            (x, y),
            cell_size / 2 - ui_size,
        )
        label = self.font.render(str(passenger.value), True, BACKGROUND_COLOR)
        desired_size = math.sqrt(2) * (cell_size - 2 * ui_size) / 2
        scale = max(label.width / desired_size, label.height / desired_size)
        scale = max(scale, 0)
        resized_label = pygame.transform.smoothscale(
            label,
            (math.floor(label.width / scale), math.floor(label.height / scale)),
        )
        bounding_box = resized_label.get_bounding_rect()
        surface.blit(
            resized_label,
            (
                x - bounding_box.width / 2 - bounding_box.x,
                y - bounding_box.height / 2 - bounding_box.y,
            ),
        )

    def get_footer(self) -> str:
        """
        Returns a string with useful messages about the room and game state:
        - server connection status
        - how long before the game starts
        - game is over
        - you have crashed + how long before you respawn
        """
        footer = [self.connection_state.value]
        if self.game_state is not None:
            assert self.room_state is not None
            assert self.slot is not None
            if self.game_state.tick >= self.room_state.game_duration_ticks:
                footer.append("Game over.")
                # No point showing additional information
                return " | ".join(footer)
            if self.game_state.buses[self.slot].respawn_at > 0:
                t = self.game_state.buses[self.slot].respawn_at - self.game_state.tick
                footer.append(f"You crashed (respawn in {max(t, 0)} ticks)")
        elif self.room_state is not None:
            t = datetime.datetime.fromtimestamp(self.room_state.created_at)
            t += datetime.timedelta(
                seconds=self.room_state.room_max_wait_game_start_seconds
            )
            d = math.floor((t - datetime.datetime.now()).total_seconds())
            if d >= 1:
                footer.append(f"game starts in {d}")
            else:
                footer.append("game is starting")
        if self.key_event is not None and self.key_event.waiting_for_input:
            footer.append("Your turn to move")
        return " | ".join(footer)

    def draw_footer(self, surface: pygame.Surface) -> int:
        """
        Draws a footer showing the connection state at the bottom of surface. Returns how
        much height was used.
        """
        footer = self.get_footer()
        text = self.font.render(footer, True, TEXT_COLOR)
        textpos = text.get_rect(
            left=self.padding, top=surface.height - text.height - self.padding
        )
        surface.blit(text, textpos)

        if self.game_state is not None:
            assert self.room_state is not None
            text = self.font.render(
                f"tick {self.game_state.tick} / {self.room_state.game_duration_ticks}",
                True,
                TEXT_COLOR,
            )
            textpos = text.get_rect(
                right=surface.width - self.padding,
                top=surface.height - text.height - self.padding,
            )
            surface.blit(text, textpos)

        return text.height + 2 * self.padding

    def draw_scores(self) -> pygame.Surface:
        """
        Draws the scores in a fresh Surface. This allows the caller to
        then re-position the scores nicely.
        """
        assert self.room_state is not None
        players = list(self.room_state.players)
        # Sort by slot
        players.sort(key=lambda p: p.slot)
        if self.game_state is not None:
            g = self.game_state
            # Re-sort by scores. Ties are sorted by slot.
            players.sort(key=lambda p: g.scores.get(p.slot, 0), reverse=True)

        grid: list[list[tuple[str, pygame.Color, int]]] = []
        for player in players:
            row: list[tuple[str, pygame.Color, int]] = []
            if player.is_staff_agent:
                row.append(("*", STAFF_BADGE_COLOR, 0))
            else:
                row.append(("", BACKGROUND_COLOR, 0))
            teamname = player.teamname
            if len(teamname) > 11:
                teamname = f"{teamname[0:10]}…"
            c = self.get_color(player.slot)
            row.append((teamname, c, 0))
            if self.game_state is not None:
                row.append((str(self.game_state.scores.get(player.slot, 0)), c, 5))
            else:
                row.append(("", BACKGROUND_COLOR, 5))
            grid.append(row)

        surface = self.text_grid(grid)
        title = self.large_font.render("Players", True, TEXT_COLOR)
        width = max(title.width, surface.width) + 2 * self.padding
        surface2 = pygame.Surface(
            (
                width,
                self.padding
                + surface.height
                + title.height
                + self.large_font.get_linesize(),
            )
        )
        pygame.draw.rect(
            surface2, BACKGROUND_COLOR, (0, 0, surface2.width, surface2.height)
        )
        y = self.padding
        textpos = title.get_rect(centerx=math.floor(surface2.width / 2), top=y)
        surface2.blit(title, textpos)
        y += title.height + self.large_font.get_linesize()

        textpos = surface.get_rect(centerx=math.floor(surface2.width / 2), top=y)
        surface2.blit(surface, textpos)

        return surface2

    def text_grid(
        self, grid: list[list[tuple[str, pygame.Color, int]]]
    ) -> pygame.Surface:
        """
        Renders a grid of text. Figures out how much space each column needs
        and then left aligns each element of the grid.

        We include some extra space which can get used up as the
        column width change (e.g. when the score goes from "9" to "10")
        """
        assert len(grid) > 0

        # Render each cell of the grid
        surfaces: list[list[pygame.Surface]] = []
        widths = [0] * len(grid[0])
        heights = [0] * len(grid[0])
        for row in grid:
            r: list[pygame.Surface] = []
            for i, (text, color, min_characters) in enumerate(row):
                s = self.font.render(text, True, color)
                r.append(s)
                width = s.width
                if min_characters > 0:
                    additional_space = self.font.size("x" * min_characters)[0]
                    width = max(s.width, additional_space)
                if i > 0:
                    width += self.padding
                widths[i] = max(widths[i], width)
                heights[i] += s.height + self.font.get_linesize()
            surfaces.append(r)

        # Render the file surface
        surface = pygame.Surface(
            (sum(widths) + len(grid[0]) * self.padding, max(heights))
        )
        pygame.draw.rect(
            surface, BACKGROUND_COLOR, (0, 0, surface.width, surface.height)
        )

        y = 0
        for row in surfaces:
            height = 0
            for i, s in enumerate(row):
                x = sum(widths[0:i]) + self.padding * i
                surface.blit(s, (x, y))
                height = max(height, s.height)
            y += height + self.font.get_linesize()
        return surface
