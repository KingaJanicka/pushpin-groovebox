"""ADD TRACK: pick the current track's synth engine (Surge XT or Monomachine).

Each track (Instrument) owns a voice per available engine and plays one at a
time. The menu works like ADD DEVICE's: it opens on the track's engine, Left
and Right move the highlight, and ADD TRACK switches the track to the
highlighted engine (saving the choice in ``track_engines.json``, read back at
startup) and closes the menu; on the track's own engine it just closes.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import push2_python

import definitions
import engine
from user_interface.display_utils import show_text

logger = logging.getLogger("engine_selection_mode")

TRACK_ENGINES_FILENAME = "track_engines.json"
ENGINE_ORDER = [engine.DEFAULT_ENGINE, engine.MONO2K_ENGINE]

LEFT = push2_python.constants.BUTTON_LEFT
RIGHT = push2_python.constants.BUTTON_RIGHT
ADD_TRACK = push2_python.constants.BUTTON_ADD_TRACK


def load_track_engines(path: str = TRACK_ENGINES_FILENAME) -> dict[str, str]:
    """Each track's chosen engine, by instrument short name ({} when none saved)."""
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logger.warning("could not read %s (%s); every track starts on its default engine", path, e)
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if v in ENGINE_ORDER}


def save_track_engine(instrument_short_name: str, engine_name: str, path: str = TRACK_ENGINES_FILENAME) -> None:
    engines = load_track_engines(path)
    engines[instrument_short_name] = engine_name
    try:
        with open(path, "w") as f:
            json.dump(engines, f, indent=2, sort_keys=True)
    except OSError as e:
        logger.warning("could not save %s (%s)", path, e)


class EngineSelectionMode(definitions.PyshaMode):
    track_engines_filename = TRACK_ENGINES_FILENAME
    selected_index = 0

    def get_settings_to_save(self) -> dict[str, Any]:
        return {}

    # ------------------------------------------------------------- helpers

    def current_instrument(self) -> Any:
        short_name = self.app.instrument_selection_mode.get_current_instrument_short_name()
        return self.app.instruments.get(short_name, None)

    def options(self) -> list[tuple[str, str, bool]]:
        """(engine name, label, available) for the current track, in button order."""
        instrument = self.current_instrument()
        available = instrument.available_engines() if instrument is not None else []
        return [(name, engine.ENGINE_LABELS[name], name in available) for name in ENGINE_ORDER]

    def close(self) -> None:
        if self.app.is_mode_active(self):
            self.app.toggle_engine_selection_mode()

    def select(self, engine_name: str) -> bool:
        """Switch the current track to ``engine_name``. Returns whether it switched."""
        instrument = self.current_instrument()
        if instrument is None:
            return False
        label = engine.ENGINE_LABELS.get(engine_name, engine_name)
        if engine_name not in instrument.available_engines():
            hint = " (build engines/m2k)" if engine_name == engine.MONO2K_ENGINE else ""
            self.app.add_display_notification(f"{label} isn't available{hint}")
            return False
        if engine_name == instrument.active_engine_name:
            return False
        presets = getattr(self.app, "preset_selection_mode", None)
        if presets is not None and instrument.active_engine_name == engine.MONO2K_ENGINE:
            presets.save_m2k_slot(instrument)            # the sound being left, kept in its slot
        if not instrument.set_active_engine(engine_name):
            return False
        if presets is not None and engine_name == engine.MONO2K_ENGINE:
            presets.restore_m2k_slot(instrument)         # its slot's saved sound, if any
        save_track_engine(instrument.name, engine_name, self.track_engines_filename)
        # The new engine's pages: start from its first device and page
        self.app.osc_mode.current_device_index_and_page = [0, 0]
        self.app.add_display_notification(f"{instrument.name}: {label}")
        self.app.buttons_need_update = True
        self.app.pads_need_update = True
        return True

    # ------------------------------------------------------------ the mode

    def activate(self) -> None:
        # Open on the track's own engine, as ADD DEVICE opens on the current device
        instrument = self.current_instrument()
        names = [name for name, _, _ in self.options()]
        active = instrument.active_engine_name if instrument is not None else None
        self.selected_index = names.index(active) if active in names else 0
        self.update_buttons()

    def deactivate(self) -> None:
        for button_name in (LEFT, RIGHT):
            self.push.buttons.set_button_color(button_name, definitions.BLACK)
        self.app.buttons_need_update = True

    def update_buttons(self) -> None:
        n = len(self.options())
        self.push.buttons.set_button_color(LEFT, definitions.WHITE if self.selected_index > 0 else definitions.BLACK)
        self.push.buttons.set_button_color(RIGHT, definitions.WHITE if self.selected_index < n - 1 else definitions.BLACK)

    def update_display(self, ctx: Any, w: int, h: int) -> None:
        # Over whatever page is underneath
        ctx.save()
        ctx.set_source_rgb(0, 0, 0)
        ctx.rectangle(0, 0, w, h)
        ctx.fill()
        ctx.restore()

        instrument = self.current_instrument()
        active = instrument.active_engine_name if instrument is not None else None
        active_label = engine.ENGINE_LABELS.get(active, "-") if active else "-"
        for idx, (name, label, available) in enumerate(self.options()):
            if idx == self.selected_index:
                background = definitions.YELLOW
            elif available:
                background = definitions.GRAY_LIGHT
            else:
                background = definitions.GRAY_DARK
            show_text(
                ctx,
                idx,
                20,
                label,
                height=25,
                font_color=definitions.BLACK,
                background_color=background,
                font_size_percentage=0.7,
                center_vertically=True,
                center_horizontally=True,
                rectangle_padding=1,
            )
        title = f"{instrument.name}: {active_label}" if instrument is not None else "No track"
        show_text(ctx, 0, 60, title, height=25, font_color=definitions.WHITE)
        show_text(ctx, 0, 100, "< > choose, ADD TRACK: select", height=20, font_color=definitions.GRAY_LIGHT)

    def on_button_pressed(self, button_name: str) -> bool | None:
        options = self.options()
        if button_name == LEFT:
            if self.selected_index > 0:
                self.selected_index -= 1
            self.update_buttons()
            return True
        if button_name == RIGHT:
            if self.selected_index < len(options) - 1:
                self.selected_index += 1
            self.update_buttons()
            return True
        if button_name == ADD_TRACK:
            name, _, available = options[self.selected_index]
            if not available:
                self.select(name)            # explains why, and the menu stays open
                return True
            self.select(name)                # (does nothing on the track's own engine)
            self.close()
            return True
        return None

    def on_encoder_rotated(self, encoder_name: str, increment: int) -> bool:
        # Nothing behind the menu should change while it hides the pages
        return True
