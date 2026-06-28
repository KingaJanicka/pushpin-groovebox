"""
RecordingContext — a drop-in replacement for cairo.Context that records
every draw call as a picklable tuple instead of executing it immediately.

The main asyncio loop uses this instead of a real cairo.Context.  All
state-mutation calls (set_source_rgb, select_font_face, …) are mirrored
on a tiny 1×1 shadow surface so that text_extents() returns accurate
measurements.  Expensive render operations (fill, stroke, show_text, …)
are only recorded — they execute in DisplayProcess, which runs in a
separate OS process and therefore has its own GIL.

This means the main process holds the GIL for only microseconds per frame
(shadow-context font queries), instead of the tens of milliseconds that a
full 960×160 Cairo render takes — eliminating the GIL starvation that
causes the isobar MIDI clock to fall behind and then catch up in bursts.
"""

from __future__ import annotations

from typing import Any

import cairo


class RecordingContext:
    """Fake cairo.Context that records drawing commands as serialisable tuples."""

    def __init__(self) -> None:
        # 1×1 surface — used only for font-state tracking and text_extents().
        _shadow_surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, 1, 1)
        self._shadow = cairo.Context(_shadow_surface)
        self.commands: list[tuple] = []

    # ── graphics state ────────────────────────────────────────────────────────

    def save(self) -> None:
        self._shadow.save()
        self.commands.append(("save",))

    def restore(self) -> None:
        self._shadow.restore()
        self.commands.append(("restore",))

    # ── colour / source ───────────────────────────────────────────────────────

    def set_source_rgb(self, r: float, g: float, b: float) -> None:
        self.commands.append(("set_source_rgb", r, g, b))

    def set_source_rgba(self, r: float, g: float, b: float, a: float) -> None:
        self.commands.append(("set_source_rgba", r, g, b, a))

    # ── font ─────────────────────────────────────────────────────────────────

    def select_font_face(self, family: str, slant: Any, weight: Any) -> None:
        # Mirror to shadow so text_extents() sees the correct font.
        self._shadow.select_font_face(family, slant, weight)
        # Store as ints — cairo enum values are ints and ints are cheaply picklable.
        self.commands.append(("select_font_face", family, int(slant), int(weight)))

    def set_font_size(self, size: float) -> None:
        self._shadow.set_font_size(size)
        self.commands.append(("set_font_size", size))

    def text_extents(self, text: str) -> tuple:
        """Delegate eagerly to the shadow context.

        Callers use the return value to compute positions for subsequent
        move_to() calls.  By resolving it here in the shadow, those
        move_to coordinates are correct when recorded, so the subprocess
        can replay the command stream verbatim without re-computing them.
        """
        return self._shadow.text_extents(text)

    def show_text(self, text: str) -> None:
        self.commands.append(("show_text", text))

    # ── path construction ─────────────────────────────────────────────────────

    def move_to(self, x: float, y: float) -> None:
        self.commands.append(("move_to", x, y))

    def line_to(self, x: float, y: float) -> None:
        self.commands.append(("line_to", x, y))

    def arc(self, xc: float, yc: float, radius: float, angle1: float, angle2: float) -> None:
        self.commands.append(("arc", xc, yc, radius, angle1, angle2))

    def rectangle(self, x: float, y: float, width: float, height: float) -> None:
        self.commands.append(("rectangle", x, y, width, height))

    def close_path(self) -> None:
        self.commands.append(("close_path",))

    # ── painting ──────────────────────────────────────────────────────────────

    def fill(self) -> None:
        self.commands.append(("fill",))

    def fill_preserve(self) -> None:
        self.commands.append(("fill_preserve",))

    def stroke(self) -> None:
        self.commands.append(("stroke",))

    def paint(self) -> None:
        self.commands.append(("paint",))

    def set_line_width(self, width: float) -> None:
        self.commands.append(("set_line_width", width))
