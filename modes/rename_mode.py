"""Renaming from the Push: a small name editor on the display.

Left/Right move the cursor (Right past the end adds a character), Up/Down
change the character under it, DELETE removes it, SELECT saves and the button
that opened the editor cancels.

Holding SHIFT shows a keyboard (a grid of every character, as Elektron's
naming screens have): the arrows move around it while SHIFT is held, and
letting go of SHIFT types the highlighted character at the cursor and moves
the cursor on to the next position.

Whoever opens the editor (``RenameMode.start``) gets the new name through
``on_confirm``, which returns None when it's done, or a message to show (the
name is taken, say) to keep the editor open.
"""
from __future__ import annotations

from typing import Any, Callable

import push2_python

import definitions

# Up goes forwards through these, Down backwards; a new character starts as a space
CHARSET = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-+_.#&()"
MAX_LENGTH = 24

# The keyboard: every character of CHARSET, a row at a time ("" is an empty cell)
KEYBOARD = [
    list("ABCDEFGHIJKL"),
    list("MNOPQRSTUVWX"),
    list("YZabcdefghij"),
    list("klmnopqrstuv"),
    list("wxyz01234567"),
    list("89-+_.#&()") + [" ", ""],
]
SPACE_LABEL = "SPC"

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

    def type(self, ch: str) -> None:
        """Put ``ch`` at the cursor and move on (at the last allowed place, stay)."""
        self.chars[self.cursor] = ch
        self.right()

    def delete(self) -> None:
        if len(self.chars) > 1:
            del self.chars[self.cursor]
            self.cursor = min(self.cursor, len(self.chars) - 1)
        else:
            self.chars = [" "]


class Keyboard:
    """Where the highlight is on KEYBOARD; the arrows wrap around its edges."""

    def __init__(self) -> None:
        self.row = 0
        self.col = 0

    @property
    def char(self) -> str:
        return KEYBOARD[self.row][self.col]

    def move(self, d_row: int, d_col: int) -> None:
        rows, cols = len(KEYBOARD), len(KEYBOARD[0])
        for _ in range(rows * cols):              # (skip empty cells)
            self.row = (self.row + d_row) % rows
            self.col = (self.col + d_col) % cols
            if self.char != "":
                return

    def go_to(self, ch: str) -> None:
        for r, row in enumerate(KEYBOARD):
            if ch in row:
                self.row, self.col = r, row.index(ch)
                return


class RenameMode(definitions.PyshaMode):
    editor: NameEditor | None = None
    keyboard: Keyboard | None = None              # open while not None
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
        self.keyboard = None
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
        self.keyboard = None

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

    def open_keyboard(self) -> None:
        self.keyboard = Keyboard()
        # start on the character under the cursor, so a small fix is a short trip
        self.keyboard.go_to(self.editor.chars[self.editor.cursor] if self.editor else "A")

    def type_and_close_keyboard(self) -> None:
        """SHIFT let go: the highlighted character goes in at the cursor, which moves on."""
        if self.keyboard is not None and self.editor is not None:
            self.editor.type(self.keyboard.char)
        self.keyboard = None

    # ------------------------------------------------------------ the mode

    BUTTONS = (B.BUTTON_LEFT, B.BUTTON_RIGHT, B.BUTTON_UP, B.BUTTON_DOWN, B.BUTTON_SELECT, B.BUTTON_DELETE,
               B.BUTTON_SHIFT)

    def activate(self) -> None:
        self.update_buttons()

    def deactivate(self) -> None:
        for name in self.BUTTONS:
            self.push.buttons.set_button_color(name, definitions.BLACK)
        self.app.buttons_need_update = True

    def update_buttons(self) -> None:
        for name in self.BUTTONS:
            self.push.buttons.set_button_color(name, definitions.WHITE)
        if self.keyboard is not None:
            self.push.buttons.set_button_color(B.BUTTON_SHIFT, definitions.YELLOW)
        if self.cancel_button:
            self.push.buttons.set_button_color(self.cancel_button, definitions.RED)

    def on_button_pressed(self, button_name: str) -> bool | None:
        if self.editor is None:
            return None
        if button_name == B.BUTTON_SHIFT:
            self.open_keyboard()
            self.update_buttons()
        elif self.keyboard is not None and button_name in (B.BUTTON_LEFT, B.BUTTON_RIGHT, B.BUTTON_UP, B.BUTTON_DOWN):
            self.keyboard.move(*{
                B.BUTTON_LEFT: (0, -1), B.BUTTON_RIGHT: (0, 1), B.BUTTON_UP: (-1, 0), B.BUTTON_DOWN: (1, 0),
            }[button_name])
        elif self.keyboard is not None and button_name == B.BUTTON_SELECT:
            return True                     # (SHIFT held: letting go of it types; SELECT waits)
        elif button_name == B.BUTTON_LEFT:
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
        if self.editor is None:
            return None
        if button_name == B.BUTTON_SHIFT and self.keyboard is not None:
            self.type_and_close_keyboard()
            self.message = ""
            self.update_buttons()
        # (SELECT released must not reach the preset browser underneath)
        return True

    def on_encoder_rotated(self, encoder_name: str, increment: int) -> bool:
        return True

    def on_pad_pressed(self, pad_n, pad_ij, velocity) -> bool:
        return True

    def on_pad_released(self, pad_n, pad_ij, velocity) -> bool:
        return True

    # ------------------------------------------------------------- drawing

    def _draw_name(self, ctx: Any, x0: int, y0: int, cell: int, height: int, font: int) -> None:
        for i, ch in enumerate(self.editor.chars):
            x = x0 + i * cell
            if i == self.editor.cursor:
                ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.YELLOW))
                ctx.rectangle(x, y0, cell - 2, height)
                ctx.fill()
                ctx.set_source_rgb(0, 0, 0)
            else:
                ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.WHITE))
            ctx.set_font_size(font)
            ctx.move_to(x + cell * 0.15, y0 + height * 0.78)
            ctx.show_text(ch if ch != " " else "_" if i == self.editor.cursor else " ")

    def _draw_keyboard(self, ctx: Any, w: int) -> None:
        cols = len(KEYBOARD[0])
        cell_w, cell_h, y0 = w // cols, 21, 30
        for r, row in enumerate(KEYBOARD):
            for c, ch in enumerate(row):
                if ch == "":
                    continue
                x, y = c * cell_w, y0 + r * cell_h
                selected = (r, c) == (self.keyboard.row, self.keyboard.col)
                if selected:
                    ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.YELLOW))
                    ctx.rectangle(x + 2, y, cell_w - 4, cell_h - 2)
                    ctx.fill()
                    ctx.set_source_rgb(0, 0, 0)
                else:
                    ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
                label = SPACE_LABEL if ch == " " else ch
                ctx.set_font_size(13 if ch == " " else 17)
                ctx.move_to(x + cell_w / 2 - (14 if ch == " " else 5), y + 16)
                ctx.show_text(label)

    def update_display(self, ctx: Any, w: int, h: int) -> None:
        if self.editor is None:
            return
        ctx.save()
        ctx.set_source_rgb(0, 0, 0)
        ctx.rectangle(0, 0, w, h)
        ctx.fill()

        import cairo  # (the display process renders the recorded calls with cairo)

        ctx.select_font_face("Monospace", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        if self.keyboard is not None:
            # the name small along the top, the keyboard below it
            self._draw_name(ctx, 8, 3, 18, 24, 18)
            ctx.set_font_size(12)
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
            ctx.move_to(8 + MAX_LENGTH * 18 + 20, 20)
            ctx.show_text("arrows choose   let go of SHIFT to type it")
            self._draw_keyboard(ctx, w)
            ctx.restore()
            return

        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
        ctx.set_font_size(14)
        ctx.move_to(12, 22)
        ctx.show_text(self.title)
        self._draw_name(ctx, 12, 40, 32, 50, 34)

        ctx.set_font_size(13)
        if self.message:
            ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.RED))
            ctx.move_to(12, 118)
            ctx.show_text(self.message)
        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
        ctx.move_to(12, 145)
        ctx.show_text("hold SHIFT keyboard   < > move   Up/Down letter   DELETE remove   SELECT save   red button cancel")
        ctx.restore()
