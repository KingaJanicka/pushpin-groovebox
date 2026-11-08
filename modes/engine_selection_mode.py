"""ADD TRACK: pick the current track's synth engine (Surge XT or Monomachine).

Each track (Instrument) owns a voice per available engine and plays one at a
time. This mode shows the engines on the upper row of buttons; pressing one
switches the current track to it, saves the choice (``track_engines.json``,
read back at startup) and closes the menu. ADD TRACK again closes it too.
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

UPPER_ROW_BUTTONS = [
    push2_python.constants.BUTTON_UPPER_ROW_1,
    push2_python.constants.BUTTON_UPPER_ROW_2,
    push2_python.constants.BUTTON_UPPER_ROW_3,
    push2_python.constants.BUTTON_UPPER_ROW_4,
    push2_python.constants.BUTTON_UPPER_ROW_5,
    push2_python.constants.BUTTON_UPPER_ROW_6,
    push2_python.constants.BUTTON_UPPER_ROW_7,
    push2_python.constants.BUTTON_UPPER_ROW_8,
]


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
        if not instrument.set_active_engine(engine_name):
            return False
        save_track_engine(instrument.name, engine_name, self.track_engines_filename)
        # The new engine's pages: start from its first device and page
        self.app.osc_mode.current_device_index_and_page = [0, 0]
        self.app.add_display_notification(f"{instrument.name}: {label}")
        self.app.buttons_need_update = True
        self.app.pads_need_update = True
        return True

    # ------------------------------------------------------------ the mode

    def activate(self) -> None:
        self.update_buttons()

    def deactivate(self) -> None:
        for button_name in UPPER_ROW_BUTTONS:
            self.push.buttons.set_button_color(button_name, definitions.BLACK)
        self.app.buttons_need_update = True

    def update_buttons(self) -> None:
        instrument = self.current_instrument()
        active = instrument.active_engine_name if instrument is not None else None
        options = self.options()
        for idx, button_name in enumerate(UPPER_ROW_BUTTONS):
            if idx >= len(options):
                color = definitions.BLACK
            else:
                name, _, available = options[idx]
                color = definitions.YELLOW if name == active else (definitions.WHITE if available else definitions.GRAY_DARK)
            self.push.buttons.set_button_color(button_name, color)

    def update_display(self, ctx: Any, w: int, h: int) -> None:
        # Over whatever page is underneath
        ctx.save()
        ctx.set_source_rgb(0, 0, 0)
        ctx.rectangle(0, 0, w, h)
        ctx.fill()
        ctx.restore()

        instrument = self.current_instrument()
        active = instrument.active_engine_name if instrument is not None else None
        for idx, (name, label, available) in enumerate(self.options()):
            if name == active:
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
        title = f"{instrument.name} engine" if instrument is not None else "No track"
        show_text(ctx, 0, 60, title, height=25, font_color=definitions.WHITE)
        show_text(ctx, 0, 100, "ADD TRACK: close", height=20, font_color=definitions.GRAY_LIGHT)

    def on_button_pressed(self, button_name: str) -> bool | None:
        if button_name in UPPER_ROW_BUTTONS:
            idx = UPPER_ROW_BUTTONS.index(button_name)
            options = self.options()
            if idx < len(options):
                switched = self.select(options[idx][0])
                if switched or options[idx][2]:
                    self.close()
                else:
                    self.update_buttons()
            return True
        return None

    def on_encoder_rotated(self, encoder_name: str, increment: int) -> bool:
        # Nothing behind the menu should change while it hides the pages
        return True
