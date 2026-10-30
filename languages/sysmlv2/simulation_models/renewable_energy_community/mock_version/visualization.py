"""pygame window for the CleanWatts mock demo (see MOCK-DEMO.md,
"Visualization" and "The loop").

`EnergyVisualization.run(model, on_start, on_tick, tick_rate)` is the
`SimulationVisualization` interface the fischertechnik demo uses, so a LipVM
driver can later pass its own `on_start`/`on_tick`. It owns the loop: every
frame, unless the clock is paused, it ticks the live simulation and the
"without changes" one together, then calls `on_tick()`, then draws.

Colours: the dataviz reference palette, light mode (projector friendly);
categorical slots in fixed order (grid import, consumption, PV, battery),
validated with the skill's validator (all checks pass; PV and battery are
below 3:1 contrast, so every line also has a direct label).
"""
import math
import os
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")  # same as factory_visualization.py: no banner on import
import pygame

from languages.sysmlv2.simulation_models.generic import SimulationVisualization
from languages.sysmlv2.simulation_models.renewable_energy_community.mock_version.applier import Applier

WINDOW_SIZE = (1280, 720)
WINDOW_HOURS = 48  # simulated hours shown

SURFACE = (252, 252, 251)
INK = (11, 11, 11)
INK_SECONDARY = (82, 81, 78)
INK_MUTED = (137, 135, 129)
GRIDLINE = (225, 224, 217)
AXIS = (195, 194, 183)
GRID_IMPORT = (42, 120, 214)    # slot 1, blue
CONSUMPTION = (235, 104, 52)    # slot 2, orange
PV = (27, 175, 122)             # slot 3, aqua
BATTERY = (237, 161, 0)         # slot 4, yellow
LIMIT = (208, 59, 59)           # status critical, always with a label
BUTTON = (42, 120, 214)
BUTTON_INK = (255, 255, 255)

MARGIN = 16
PANEL_WIDTH = 330
AXIS_WIDTH = 44
LABEL_GUTTER = 120  # right of the charts, for the direct labels at the line ends


@dataclass(frozen=True)
class DemoMessage:
    """A line in the message area: an applied or rejected save."""
    hour: int
    kind: str          # "applied", "rejected", or "saved" (a save without changes)
    lines: tuple


def clock_text(hour: int) -> str:
    return f"Day {hour // 24 + 1} {hour % 24:02d}:00"


def _figures(records) -> dict:
    """Totals over `records` (one per hour, so kW = kWh)."""
    grid_import = sum(max(0.0, r.grid_import) for r in records)
    export = sum(max(0.0, -r.grid_import) for r in records)
    pv = sum(r.pv for r in records)
    return {
        "Grid import": f"{grid_import:.1f} kWh",
        "Export": f"{export:.1f} kWh",
        "Peak import": f"{max((r.grid_import for r in records), default=0.0):.1f} kW",
        "Own solar used": f"{100 * (1 - export / pv):.0f} %" if pv > 0 else "-",
        "Cost": f"EUR {sum(max(0.0, r.grid_import) * r.price for r in records):.2f}",
    }


class EnergyVisualization(SimulationVisualization):
    """`applier` drives the live simulation (`run`'s `model` must be its
    simulation); `baseline`, if given, the "without changes" one.
    `is_paused` stops the clock (e.g. while the model reloads); `post()`
    adds a line to the message area.
    """

    def __init__(self, applier: Applier, baseline: Optional[Applier] = None,
                 is_paused: Callable[[], bool] = lambda: False, title: str = "household.sysml"):
        self.applier = applier
        self.baseline = baseline
        self.is_paused = is_paused
        self.title = title
        self.messages: deque[DemoMessage] = deque(maxlen=3)

    def post(self, kind: str, lines: list[str]) -> None:
        self.messages.appendleft(DemoMessage(self.applier.simulation.hour, kind, tuple(lines)))

    # -- Loop -------------------------------------------------------------------

    def run(self, model, on_start=lambda: None, on_tick=lambda: None, tick_rate: int = 60) -> None:
        if model is not self.applier.simulation:
            raise ValueError("run()'s model must be the applier's simulation")

        pygame.init()
        screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        pygame.display.set_caption("CleanWatts mock demo")
        clock = pygame.time.Clock()
        self._fonts = {
            "small": pygame.font.SysFont(None, 18),
            "normal": pygame.font.SysFont(None, 21),
            "bold": pygame.font.SysFont(None, 21, bold=True),
            "title": pygame.font.SysFont(None, 30, bold=True),
            "big": pygame.font.SysFont(None, 44, bold=True),
        }

        started = False
        start_button: Optional[pygame.Rect] = None
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not started
                      and start_button is not None and start_button.collidepoint(event.pos)):
                    on_start()
                    started = True

            if started:
                if not self.is_paused():
                    model.tick()
                    if self.baseline is not None:
                        self.baseline.simulation.tick()
                on_tick()

            screen.fill(SURFACE)
            if started:
                self._draw_dashboard(screen)
            else:
                start_button = self._draw_start(screen)
            pygame.display.flip()
            clock.tick(tick_rate)

        pygame.quit()

    # -- Text helpers -------------------------------------------------------------

    def _text(self, screen, text, pos, font="normal", color=INK, anchor="topleft") -> pygame.Rect:
        surface = self._fonts[font].render(text, True, color)
        rect = surface.get_rect(**{anchor: pos})
        screen.blit(surface, rect)
        return rect

    # -- Start screen ----------------------------------------------------------

    def _draw_start(self, screen) -> pygame.Rect:
        width, height = screen.get_size()
        center_x = width // 2
        self._text(screen, "CleanWatts mock demo", (center_x, height // 2 - 90), "big", anchor="center")
        self._text(screen, f"A household simulated hour by hour from {self.title}. Edit and save the model while it runs.",
                   (center_x, height // 2 - 45), "normal", INK_SECONDARY, anchor="center")
        button = pygame.Rect(0, 0, 160, 48)
        button.center = (center_x, height // 2 + 20)
        pygame.draw.rect(screen, BUTTON, button, border_radius=6)
        self._text(screen, "Start", button.center, "title", BUTTON_INK, anchor="center")
        return button

    # -- Dashboard -----------------------------------------------------------------

    def _draw_dashboard(self, screen) -> None:
        width, height = screen.get_size()
        simulation = self.applier.simulation
        controller = self.applier.controller

        # Header: title, clock, algorithm, status.
        self._text(screen, f"CleanWatts mock demo  -  {self.title}", (MARGIN, MARGIN), "title")
        self._text(screen, clock_text(simulation.hour), (width - MARGIN, MARGIN), "title", anchor="topright")
        algorithm = f"Battery algorithm: {controller.algorithm}  ({controller.state or '-'})" if controller else ""
        self._text(screen, algorithm, (MARGIN, MARGIN + 30), "bold", INK_SECONDARY)
        if self.is_paused():
            self._text(screen, "Reloading model...  clock paused", (width - MARGIN, MARGIN + 30), "bold",
                       INK, anchor="topright")

        top = MARGIN + 62
        messages_height = 66
        chart_left = MARGIN + AXIS_WIDTH
        chart_right = width - PANEL_WIDTH - 2 * MARGIN - LABEL_GUTTER
        available = height - top - messages_height - MARGIN
        power_rect = pygame.Rect(chart_left, top + 26, chart_right - chart_left, int(available * 0.64) - 26)
        soc_top = power_rect.bottom + 34
        soc_rect = pygame.Rect(chart_left, soc_top + 22, power_rect.width, top + available - soc_top - 22 - 18)

        end_hour = simulation.hour
        start_hour = end_hour - WINDOW_HOURS
        live = [r for r in simulation.history if r.hour >= start_hour]
        base = [r for r in self.baseline.simulation.history if r.hour >= start_hour] if self.baseline else []

        self._draw_power_chart(screen, power_rect, start_hour, live, base)
        self._draw_soc_chart(screen, soc_rect, start_hour, live, base)
        self._draw_events(screen, power_rect, soc_rect, start_hour)
        self._draw_panel(screen, pygame.Rect(width - PANEL_WIDTH - MARGIN, top, PANEL_WIDTH, height - top - MARGIN))
        self._draw_messages(screen, pygame.Rect(MARGIN, height - MARGIN - messages_height,
                                                chart_right + LABEL_GUTTER - MARGIN, messages_height))

    def _x(self, rect: pygame.Rect, start_hour: int, hour: float) -> float:
        """x of the middle of simulated hour `hour`."""
        return rect.left + (hour - start_hour + 0.5) * rect.width / WINDOW_HOURS

    def _draw_time_axis(self, screen, rect: pygame.Rect, start_hour: int, labels: bool) -> None:
        for hour in range(start_hour, start_hour + WINDOW_HOURS + 1):
            if hour % 6:
                continue
            x = rect.left + (hour - start_hour) * rect.width / WINDOW_HOURS
            midnight = hour % 24 == 0
            pygame.draw.line(screen, AXIS if midnight else GRIDLINE, (x, rect.top), (x, rect.bottom), 1)
            if labels and hour >= 0:
                text = f"Day {hour // 24 + 1}" if midnight else f"{hour % 24:02d}:00"
                self._text(screen, text, (x, rect.bottom + 4), "bold" if midnight else "small",
                           INK_SECONDARY if midnight else INK_MUTED, anchor="midtop")

    def _draw_power_chart(self, screen, rect, start_hour, live, base) -> None:
        battery = self.applier.simulation.battery
        # Fixed range covering the story's figures, widened (never narrowed)
        # when the data or the limit line goes beyond it.
        values = [v for r in live + base for v in (r.grid_import, r.load, r.pv)]
        y_min = float(math.floor(min([-4.0] + values)))
        y_max = float(math.ceil(max([9.0, battery.peakLimit + 1.0] + values)))

        def y(value: float) -> float:
            return rect.bottom - (value - y_min) / (y_max - y_min) * rect.height

        self._legend(screen, rect.left, rect.top - 24, [
            ("Grid import", GRID_IMPORT, False), ("Grid import without changes", INK_MUTED, True),
            ("Consumption", CONSUMPTION, False), ("Solar PV", PV, False),
            (f"Grid limit (peakLimit)", LIMIT, True),
        ])
        self._text(screen, "kW", (rect.left - 8, rect.top - 22), "small", INK_MUTED, anchor="topright")
        step = 2 if y_max - y_min <= 20 else 5
        value = (int(y_min) // step) * step
        while value <= y_max:
            if value >= y_min:
                pygame.draw.line(screen, AXIS if value == 0 else GRIDLINE, (rect.left, y(value)), (rect.right, y(value)), 1)
                self._text(screen, f"{value:g}", (rect.left - 6, y(value)), "small", INK_MUTED, anchor="midright")
            value += step
        self._draw_time_axis(screen, rect, start_hour, labels=True)

        limit_y = y(battery.peakLimit)
        _dashed_line(screen, LIMIT, (rect.left, limit_y), (rect.right, limit_y), 2)
        self._text(screen, f"grid limit {battery.peakLimit:g} kW", (rect.left + 4, limit_y - 2), "small",
                   INK_SECONDARY, anchor="bottomleft")

        if base:
            _dashed_polyline(screen, INK_MUTED, [(self._x(rect, start_hour, r.hour), y(r.grid_import)) for r in base], 2)
        series = [("PV", PV, lambda r: r.pv, 2), ("consumption", CONSUMPTION, lambda r: r.load, 2),
                  ("grid import", GRID_IMPORT, lambda r: r.grid_import, 3)]
        end_labels = []
        for label, color, get, line_width in series:
            points = [(self._x(rect, start_hour, r.hour), y(get(r))) for r in live]
            if len(points) >= 2:
                pygame.draw.lines(screen, color, False, points, line_width)
            if points:
                end_labels.append((points[-1], color, f"{label} {get(live[-1]):.1f} kW"))
        self._end_labels(screen, rect.right, end_labels)

    def _draw_soc_chart(self, screen, rect, start_hour, live, base) -> None:
        self._text(screen, "Battery charge level", (rect.left, rect.top - 22), "bold", INK_SECONDARY)
        self._legend(screen, rect.left + 190, rect.top - 22, [("without changes", INK_MUTED, True)])

        def y(soc: float) -> float:
            return rect.bottom - soc * rect.height

        for level in (0.0, 0.5, 1.0):
            pygame.draw.line(screen, AXIS if level == 0 else GRIDLINE, (rect.left, y(level)), (rect.right, y(level)), 1)
            self._text(screen, f"{level * 100:.0f}%", (rect.left - 6, y(level)), "small", INK_MUTED, anchor="midright")
        self._draw_time_axis(screen, rect, start_hour, labels=False)

        if base:
            _dashed_polyline(screen, INK_MUTED, [(self._x(rect, start_hour, r.hour), y(r.soc)) for r in base], 2)
        points = [(self._x(rect, start_hour, r.hour), y(r.soc)) for r in live]
        if len(points) >= 2:
            pygame.draw.lines(screen, BATTERY, False, points, 2)
        if points:
            self._end_labels(screen, rect.right, [(points[-1], BATTERY, f"{live[-1].soc * 100:.0f}%")])

    def _draw_events(self, screen, power_rect, soc_rect, start_hour) -> None:
        """A labelled vertical line at the start of the hour each save was
        applied; labels staggered in three rows so close events stay legible.
        """
        visible = [applied for applied in self.applier.applied if applied.hour >= start_hour]
        for index, applied in enumerate(visible):
            x = power_rect.left + (applied.hour - start_hour) * power_rect.width / WINDOW_HOURS
            pygame.draw.line(screen, INK, (x, power_rect.top), (x, soc_rect.bottom), 1)
            label_y = power_rect.top + 4 + (index % 3) * 18
            label = ", ".join(applied.labels())
            surface = self._fonts["small"].render(label, True, INK)
            box = surface.get_rect(topleft=(x + 4, label_y)).inflate(6, 2)
            if box.right > power_rect.right:  # flip to the left of the line near the right edge
                box.right = x - 2
            pygame.draw.rect(screen, SURFACE, box)
            pygame.draw.rect(screen, GRIDLINE, box, 1)
            screen.blit(surface, surface.get_rect(center=box.center))

    def _draw_panel(self, screen, rect) -> None:
        pygame.draw.line(screen, GRIDLINE, (rect.left - MARGIN // 2, rect.top), (rect.left - MARGIN // 2, rect.bottom), 1)
        x, y = rect.left, rect.top
        simulation = self.applier.simulation

        self._text(screen, "Last 24 hours", (x, y), "bold")
        self._text(screen, "now", (x + 175, y), "small", INK_SECONDARY, anchor="topright")
        if self.baseline:
            self._text(screen, "without changes", (rect.right, y), "small", INK_SECONDARY, anchor="topright")
        y += 22
        live = _figures(list(simulation.history)[-24:])
        base = _figures(list(self.baseline.simulation.history)[-24:]) if self.baseline else {}
        for name, value in live.items():
            self._text(screen, name, (x, y), "normal", INK_SECONDARY)
            self._text(screen, value, (x + 175, y), "bold", anchor="topright")
            if base:
                self._text(screen, base[name], (rect.right, y), "normal", INK_SECONDARY, anchor="topright")
            y += 22

        y += 14
        battery = simulation.battery
        self._text(screen, "Battery", (x, y), "bold")
        y += 22
        for name, value in [("Charge level", f"{battery.soc * 100:.0f} %"),
                            ("Capacity", f"{battery.capacity:g} kWh, max {battery.maxPower:g} kW"),
                            ("Action", battery.mode)]:
            self._text(screen, name, (x, y), "normal", INK_SECONDARY)
            self._text(screen, value, (rect.right, y), "normal", anchor="topright")
            y += 22

        y += 14
        self._text(screen, "Devices in the household", (x, y), "bold")
        y += 22
        rows = [(simulation.pv.name, "PV", f"{simulation.pv.pvPeak:g} kWp")]
        rows += [(device.name, type(device).__name__.removeprefix("Mock"), f"{device.load:.1f} kW")
                 for device in simulation.devices]
        for name, part_def, value in rows:
            self._text(screen, f"{name.rsplit('::', 1)[-1]}", (x, y), "normal")
            self._text(screen, part_def, (x + 120, y), "small", INK_MUTED)
            self._text(screen, value, (rect.right, y), "normal", anchor="topright")
            y += 22

    def _draw_messages(self, screen, rect) -> None:
        pygame.draw.line(screen, GRIDLINE, (rect.left, rect.top - 6), (rect.right, rect.top - 6), 1)
        y = rect.top
        for message in self.messages:
            if y > rect.bottom - 18:
                break
            rejected = message.kind == "rejected"
            badge = {"applied": "APPLIED", "rejected": "REJECTED"}.get(message.kind, "SAVED")
            badge_rect = self._text(screen, badge, (rect.left, y), "bold", LIMIT if rejected else INK)
            text = f"{clock_text(message.hour)}   " + "   ".join(message.lines)
            self._text(screen, text, (badge_rect.right + 8, y + 1), "normal", INK if rejected else INK_SECONDARY)
            y += 22

    def _legend(self, screen, x, y, entries) -> None:
        for label, color, dashed in entries:
            if dashed:
                _dashed_line(screen, color, (x, y + 8), (x + 22, y + 8), 2)
            else:
                pygame.draw.line(screen, color, (x, y + 8), (x + 22, y + 8), 3)
            x = self._text(screen, label, (x + 28, y), "small", INK_SECONDARY).right + 16

    def _end_labels(self, screen, x, labels, spacing=16) -> None:
        """A dot at each line's last point and its label in the gutter right
        of `x`, pushed apart vertically so labels never overlap.
        """
        placed = []
        for point, color, text in sorted(labels, key=lambda label: label[0][1]):
            label_y = max(point[1], placed[-1] + spacing) if placed else point[1]
            placed.append(label_y)
            pygame.draw.circle(screen, color, point, 4)
            pygame.draw.line(screen, color, point, (x + 6, label_y), 1)
            self._text(screen, text, (x + 10, label_y), "small", INK, anchor="midleft")


def _dashed_line(screen, color, start, end, width, dash=8, gap=6) -> None:
    _dashed_polyline(screen, color, [start, end], width, dash, gap)


def _dashed_polyline(screen, color, points, width, dash=8, gap=6) -> None:
    """A dashed line through `points`, the dash pattern continuing across
    segments.
    """
    drawing, remaining = True, dash
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        position = 0.0
        while position < length:
            step = min(remaining, length - position)
            if drawing:
                t1, t2 = position / length, (position + step) / length
                pygame.draw.line(screen, color, (x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1),
                                 (x1 + (x2 - x1) * t2, y1 + (y2 - y1) * t2), width)
            position += step
            remaining -= step
            if remaining <= 0:
                drawing = not drawing
                remaining = dash if drawing else gap
