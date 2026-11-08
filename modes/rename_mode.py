"""Renaming from the Push: a small name editor on the display.

Left/Right move the cursor (Right past the end adds a character), Up/Down
change the character under it, DELETE removes it, SELECT saves and the button
that opened the editor cancels. Whoever opens it (``RenameMode.start``) gets the
new name through ``on_confirm``, which returns None when it's done, or a
message to show (the name is taken, say) to keep the editor open.
"""
from __future__ import annotations

from typing import Any, Callable

import push2_python

import definitions

# Up goes forwards through these, Down backwards; a new character starts as a space
CHARSET = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-+_.#&()"
MAX_LENGTH = 24

B = push2_python.constants


class NameEditor:
    """The text and the cursor; the Push buttons call these."""

    def __init__(self, text: str = "", max_length: int = MAX_LENGTH) -> None:
        # Characters the charset lacks can't be typed; keep them as they are
        self.chars = list(text[:max_length]) or [" "]
        self.cursor = 0
        self.max_length = max_length

    @property
    def text(self) -> str:
        return "".join(self.chars)

    def left(self) -> None:
        if self.cursor > 0:
            self.cursor -= 1
            # leaving a trailing blank behind drops it
            while len(self.chars) > 1 and self.cursor < len(self.chars) - 1 and self.chars[-1] == " ":
                self.chars.pop()

    def right(self) -> None:
        if self.cursor < len(self.chars) - 1:
            self.cursor += 1
        elif len(self.chars) < self.max_length:
            self.chars.append(" ")
            self.cursor += 1

    def change(self, step: int) -> None:
        current = self.chars[self.cursor]
        i = CHARSET.find(current)
        if i < 0:
            i = 0 if step > 0 else 1
        self.chars[self.cursor] = CHARSET[(i + step) % len(CHARSET)]

    def delete(self) -> None:
        if len(self.chars) > 1:
            del self.chars[self.cursor]
            self.cursor = min(self.cursor, len(self.chars) - 1)
        else:
            self.chars = [" "]


class RenameMode(definitions.PyshaMode):
    editor: NameEditor | None = None
    title = ""
    message = ""
    on_confirm: Callable[[str], str | None] | None = None
    cancel_button: str | None = None

    def get_settings_to_save(self) -> dict[str, Any]:
        return {}

    def start(self, title: str, name: str, on_confirm: Callable[[str], str | None], cancel_button: str) -> None:
        """Open the editor on ``name``; ``cancel_button`` (the button that opened it) closes it."""
        self.title = title
        self.editor = NameEditor(name)
        self.message = ""
        self.on_confirm = on_confirm
        self.cancel_button = cancel_button
        if not self.app.is_mode_active(self):
            self.app.active_modes = self.app.active_modes + [self]
            self.activate()

    def close(self) -> None:
        if self.app.is_mode_active(self):
            self.app.active_modes = [m for m in self.app.active_modes if m != self]
            self.deactivate()
        self.editor = None

    def confirm(self) -> None:
        name = self.editor.text.strip() if self.editor else ""
        if not name:
            self.message = "A name can't be empty"
            return
        result = self.on_confirm(name) if self.on_confirm else None
        if result:
            self.message = result
            return
        self.close()

    # ------------------------------------------------------------ the mode

    BUTTONS = (B.BUTTON_LEFT, B.BUTTON_RIGHT, B.BUTTON_UP, B.BUTTON_DOWN, B.BUTTON_SELECT, B.BUTTON_DELETE)

    def activate(self) -> None:
        self.update_buttons()

    def deactivate(self) -> None:
        for name in self.BUTTONS:
            self.push.buttons.set_button_color(name, definitions.BLACK)
        self.app.buttons_need_update = True

    def update_buttons(self) -> None:
        for name in self.BUTTONS:
            self.push.buttons.set_button_color(name, definitions.WHITE)
        if self.cancel_button:
            self.push.buttons.set_button_color(self.cancel_button, definitions.RED)

    def on_button_pressed(self, button_name: str) -> bool | None:
        if self.editor is None:
            return None
        if button_name == B.BUTTON_LEFT:
            self.editor.left()
        elif button_name == B.BUTTON_RIGHT:
            self.editor.right()
        elif button_name == B.BUTTON_UP:
            self.editor.change(1)
        elif button_name == B.BUTTON_DOWN:
            self.editor.change(-1)
        elif button_name == B.BUTTON_DELETE:
            self.editor.delete()
        elif button_name == B.BUTTON_SELECT:
            self.confirm()
            return True
        elif button_name == self.cancel_button:
            self.close()
            return True
        else:
            return True                     # nothing else acts while the name is being edited
        self.message = ""
        return True

    def on_button_released(self, button_name: str) -> bool | None:
        # (SELECT released must not reach the preset browser underneath)
        return True if self.editor is not None else None

    def on_encoder_rotated(self, encoder_name: str, increment: int) -> bool:
        return True

    def on_pad_pressed(self, pad_n, pad_ij, velocity) -> bool:
        return True

    def on_pad_released(self, pad_n, pad_ij, velocity) -> bool:
        return True

    def update_display(self, ctx: Any, w: int, h: int) -> None:
        if self.editor is None:
            return
        ctx.save()
        ctx.set_source_rgb(0, 0, 0)
        ctx.rectangle(0, 0, w, h)
        ctx.fill()

        import cairo  # (the display process renders the recorded calls with cairo)

        ctx.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
        ctx.set_font_size(14)
        ctx.move_to(12, 22)
        ctx.show_text(self.title)

        cell, x0, y0, height = 32, 12, 40, 50
        for i, ch in enumerate(self.editor.chars):
            x = x0 + i * cell
            if i == self.editor.cursor:
                ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.YELLOW))
                ctx.rectangle(x, y0, cell - 2, height)
                ctx.fill()
                ctx.set_source_rgb(0, 0, 0)
            else:
                ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.WHITE))
            ctx.set_font_size(34)
            ctx.move_to(x + 5, y0 + 38)
            ctx.show_text(ch if ch != " " else "_" if i == self.editor.cursor else " ")

        ctx.set_font_size(13)
        if self.message:
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.RED))
            ctx.move_to(12, 118)
            ctx.show_text(self.message)
        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
        ctx.move_to(12, 145)
        ctx.show_text("< > move   Up/Down letter   DELETE remove   SELECT save   red button cancel")
        ctx.restore()
