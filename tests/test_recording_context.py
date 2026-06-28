"""
Tests for RecordingContext and the _replay round-trip.

Two concerns:
  1. RecordingContext records the right tuples for every drawing operation.
  2. _replay() faithfully re-executes those tuples on a real cairo.Context,
     producing an identical pixel result to drawing directly.
"""

import cairo
import numpy as np
import pytest
from unittest.mock import MagicMock, call

from user_interface.recording_context import RecordingContext
from user_interface.display_process import _replay


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _surface_to_array(surface: cairo.ImageSurface) -> np.ndarray:
    """Return an ARGB32 surface as an (H, W, 4) uint8 array."""
    h, w = surface.get_height(), surface.get_width()
    buf = surface.get_data()
    return np.ndarray(shape=(h, w, 4), dtype=np.uint8, buffer=buf).copy()


def _draw_direct(ctx: cairo.Context) -> None:
    """Reference scene drawn directly on a real cairo.Context."""
    ctx.set_source_rgb(0.0, 0.0, 0.0)
    ctx.paint()

    ctx.save()
    ctx.set_source_rgba(1.0, 0.0, 0.0, 0.8)
    ctx.rectangle(2, 3, 6, 4)
    ctx.fill()
    ctx.restore()

    ctx.set_source_rgb(0.0, 1.0, 0.0)
    ctx.move_to(0, 0)
    ctx.line_to(10, 10)
    ctx.set_line_width(1.5)
    ctx.stroke()

    ctx.select_font_face(
        "sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD
    )
    ctx.set_font_size(8)
    ctx.move_to(1, 9)
    ctx.show_text("Hi")

    ctx.set_source_rgb(0.0, 0.0, 1.0)
    ctx.arc(5, 5, 2, 0, 6.28)
    ctx.fill_preserve()
    ctx.set_line_width(0.5)
    ctx.stroke()

    ctx.move_to(1, 1)
    ctx.line_to(9, 1)
    ctx.close_path()
    ctx.set_line_width(1.0)
    ctx.stroke()


# ---------------------------------------------------------------------------
# RecordingContext — command tuple tests
# ---------------------------------------------------------------------------

class TestRecordingContextCommands:
    def setup_method(self):
        self.rc = RecordingContext()

    def test_initial_commands_empty(self):
        assert self.rc.commands == []

    def test_save_restore(self):
        self.rc.save()
        self.rc.restore()
        assert self.rc.commands == [("save",), ("restore",)]

    def test_set_source_rgb(self):
        self.rc.set_source_rgb(0.1, 0.2, 0.3)
        assert self.rc.commands == [("set_source_rgb", 0.1, 0.2, 0.3)]

    def test_set_source_rgba(self):
        self.rc.set_source_rgba(0.1, 0.2, 0.3, 0.4)
        assert self.rc.commands == [("set_source_rgba", 0.1, 0.2, 0.3, 0.4)]

    def test_select_font_face_stores_int_enums(self):
        self.rc.select_font_face(
            "monospace", cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD
        )
        cmd = self.rc.commands[0]
        assert cmd[0] == "select_font_face"
        assert cmd[1] == "monospace"
        assert isinstance(cmd[2], int)
        assert isinstance(cmd[3], int)
        assert cmd[2] == int(cairo.FONT_SLANT_ITALIC)
        assert cmd[3] == int(cairo.FONT_WEIGHT_BOLD)

    def test_set_font_size(self):
        self.rc.set_font_size(14.0)
        assert self.rc.commands == [("set_font_size", 14.0)]

    def test_select_font_face_mirrors_to_shadow_for_extents(self):
        # After selecting a font, text_extents() should use that font.
        self.rc.select_font_face(
            "sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
        )
        self.rc.set_font_size(12)
        extents = self.rc.text_extents("W")
        assert extents[2] > 0  # width > 0

    def test_text_extents_not_recorded(self):
        self.rc.text_extents("anything")
        assert not any(cmd[0] == "text_extents" for cmd in self.rc.commands)

    def test_text_extents_returns_six_tuple(self):
        extents = self.rc.text_extents("Hello")
        assert len(extents) == 6

    def test_show_text(self):
        self.rc.show_text("abc")
        assert self.rc.commands == [("show_text", "abc")]

    def test_move_to(self):
        self.rc.move_to(5.0, 10.0)
        assert self.rc.commands == [("move_to", 5.0, 10.0)]

    def test_line_to(self):
        self.rc.line_to(15.0, 25.0)
        assert self.rc.commands == [("line_to", 15.0, 25.0)]

    def test_arc(self):
        self.rc.arc(1, 2, 3, 0, 3.14)
        assert self.rc.commands == [("arc", 1, 2, 3, 0, 3.14)]

    def test_rectangle(self):
        self.rc.rectangle(1, 2, 3, 4)
        assert self.rc.commands == [("rectangle", 1, 2, 3, 4)]

    def test_close_path(self):
        self.rc.close_path()
        assert self.rc.commands == [("close_path",)]

    def test_fill(self):
        self.rc.fill()
        assert self.rc.commands == [("fill",)]

    def test_fill_preserve(self):
        self.rc.fill_preserve()
        assert self.rc.commands == [("fill_preserve",)]

    def test_stroke(self):
        self.rc.stroke()
        assert self.rc.commands == [("stroke",)]

    def test_paint(self):
        self.rc.paint()
        assert self.rc.commands == [("paint",)]

    def test_set_line_width(self):
        self.rc.set_line_width(2.5)
        assert self.rc.commands == [("set_line_width", 2.5)]

    def test_command_ordering_preserved(self):
        self.rc.set_source_rgb(1, 0, 0)
        self.rc.rectangle(0, 0, 10, 10)
        self.rc.fill()
        assert [c[0] for c in self.rc.commands] == [
            "set_source_rgb", "rectangle", "fill"
        ]


# ---------------------------------------------------------------------------
# _replay — mock-based dispatch tests
# ---------------------------------------------------------------------------

class TestReplay:
    def setup_method(self):
        self.ctx = MagicMock(spec=cairo.Context)

    def test_replay_save(self):
        _replay(self.ctx, [("save",)])
        self.ctx.save.assert_called_once_with()

    def test_replay_restore(self):
        _replay(self.ctx, [("restore",)])
        self.ctx.restore.assert_called_once_with()

    def test_replay_set_source_rgb(self):
        _replay(self.ctx, [("set_source_rgb", 0.1, 0.2, 0.3)])
        self.ctx.set_source_rgb.assert_called_once_with(0.1, 0.2, 0.3)

    def test_replay_set_source_rgba(self):
        _replay(self.ctx, [("set_source_rgba", 0.1, 0.2, 0.3, 0.4)])
        self.ctx.set_source_rgba.assert_called_once_with(0.1, 0.2, 0.3, 0.4)

    def test_replay_select_font_face(self):
        _replay(self.ctx, [("select_font_face", "mono", 0, 1)])
        self.ctx.select_font_face.assert_called_once_with("mono", 0, 1)

    def test_replay_set_font_size(self):
        _replay(self.ctx, [("set_font_size", 12.0)])
        self.ctx.set_font_size.assert_called_once_with(12.0)

    def test_replay_show_text(self):
        _replay(self.ctx, [("show_text", "hello")])
        self.ctx.show_text.assert_called_once_with("hello")

    def test_replay_move_to(self):
        _replay(self.ctx, [("move_to", 1.0, 2.0)])
        self.ctx.move_to.assert_called_once_with(1.0, 2.0)

    def test_replay_line_to(self):
        _replay(self.ctx, [("line_to", 3.0, 4.0)])
        self.ctx.line_to.assert_called_once_with(3.0, 4.0)

    def test_replay_arc(self):
        _replay(self.ctx, [("arc", 5, 5, 2, 0, 6.28)])
        self.ctx.arc.assert_called_once_with(5, 5, 2, 0, 6.28)

    def test_replay_rectangle(self):
        _replay(self.ctx, [("rectangle", 1, 2, 3, 4)])
        self.ctx.rectangle.assert_called_once_with(1, 2, 3, 4)

    def test_replay_close_path(self):
        _replay(self.ctx, [("close_path",)])
        self.ctx.close_path.assert_called_once_with()

    def test_replay_fill(self):
        _replay(self.ctx, [("fill",)])
        self.ctx.fill.assert_called_once_with()

    def test_replay_fill_preserve(self):
        _replay(self.ctx, [("fill_preserve",)])
        self.ctx.fill_preserve.assert_called_once_with()

    def test_replay_stroke(self):
        _replay(self.ctx, [("stroke",)])
        self.ctx.stroke.assert_called_once_with()

    def test_replay_paint(self):
        _replay(self.ctx, [("paint",)])
        self.ctx.paint.assert_called_once_with()

    def test_replay_set_line_width(self):
        _replay(self.ctx, [("set_line_width", 1.5)])
        self.ctx.set_line_width.assert_called_once_with(1.5)

    def test_replay_empty_command_list(self):
        _replay(self.ctx, [])
        self.ctx.assert_not_called()

    def test_replay_sequence_order(self):
        """Commands are dispatched in the order they were recorded."""
        commands = [
            ("set_source_rgb", 1, 0, 0),
            ("rectangle", 0, 0, 5, 5),
            ("fill",),
        ]
        _replay(self.ctx, commands)
        assert self.ctx.method_calls == [
            call.set_source_rgb(1, 0, 0),
            call.rectangle(0, 0, 5, 5),
            call.fill(),
        ]

    def test_replay_unknown_op_is_silently_ignored(self):
        """Unrecognised opcodes must not crash — forward-compatibility."""
        _replay(self.ctx, [("unknown_future_op", 1, 2, 3)])
        self.ctx.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: RecordingContext → _replay produces identical pixels
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """Record a scene with RecordingContext, replay on a real cairo.Context,
    and compare pixel-for-pixel against drawing the same scene directly."""

    W, H = 20, 20

    def _make_surface(self):
        return cairo.ImageSurface(cairo.FORMAT_ARGB32, self.W, self.H)

    def test_recorded_scene_matches_direct_render(self):
        # Draw directly.
        direct_surface = self._make_surface()
        _draw_direct(cairo.Context(direct_surface))
        direct_pixels = _surface_to_array(direct_surface)

        # Record then replay.
        rc = RecordingContext()
        _draw_direct(rc)
        replay_surface = self._make_surface()
        _replay(cairo.Context(replay_surface), rc.commands)
        replay_pixels = _surface_to_array(replay_surface)

        assert np.array_equal(direct_pixels, replay_pixels), (
            "Replayed frame does not match direct render pixel-for-pixel"
        )

    def test_paint_fills_entire_surface(self):
        rc = RecordingContext()
        rc.set_source_rgb(1.0, 0.0, 0.0)  # red
        rc.paint()

        surface = self._make_surface()
        _replay(cairo.Context(surface), rc.commands)
        pixels = _surface_to_array(surface)

        # ARGB32 in memory (little-endian): B, G, R, A
        assert np.all(pixels[:, :, 2] == 255), "Red channel should be 255 everywhere"
        assert np.all(pixels[:, :, 1] == 0),   "Green channel should be 0 everywhere"
        assert np.all(pixels[:, :, 0] == 0),   "Blue channel should be 0 everywhere"

    def test_rectangle_fill_paints_correct_region(self):
        rc = RecordingContext()
        rc.set_source_rgb(0.0, 0.0, 0.0)
        rc.paint()
        rc.set_source_rgb(0.0, 1.0, 0.0)  # green rectangle
        rc.rectangle(5, 5, 10, 10)
        rc.fill()

        surface = self._make_surface()
        _replay(cairo.Context(surface), rc.commands)
        pixels = _surface_to_array(surface)

        # Inside rectangle (pixel 10, 10): green
        assert pixels[10, 10, 1] == 255, "Green channel inside rect should be 255"
        assert pixels[10, 10, 2] == 0,   "Red channel inside rect should be 0"
        # Outside rectangle (pixel 1, 1): black
        assert pixels[1, 1, 1] == 0, "Green channel outside rect should be 0"

    def test_save_restore_isolates_state(self):
        """save/restore must actually scope the graphics state in the replay."""
        rc = RecordingContext()
        rc.set_source_rgb(1.0, 1.0, 1.0)  # white background
        rc.paint()
        rc.save()
        rc.set_source_rgb(1.0, 0.0, 0.0)  # red inside save
        rc.rectangle(0, 0, 5, 5)
        rc.fill()
        rc.restore()
        # After restore, source should revert to white.
        rc.rectangle(10, 10, 5, 5)
        rc.fill()

        surface = self._make_surface()
        _replay(cairo.Context(surface), rc.commands)
        pixels = _surface_to_array(surface)

        # Top-left 5×5 square: red
        assert pixels[2, 2, 2] == 255, "Red channel inside save block should be 255"
        # Bottom-right 5×5 square: white (restored source)
        assert pixels[12, 12, 2] == 255, "Red channel after restore should be 255"
        assert pixels[12, 12, 1] == 255, "Green channel after restore should be 255"
        assert pixels[12, 12, 0] == 255, "Blue channel after restore should be 255"
