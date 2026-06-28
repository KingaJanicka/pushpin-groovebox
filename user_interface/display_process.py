"""
DisplayProcess — runs Cairo rendering in a separate OS process.

Why a process and not a thread?  pycairo does not release the GIL during
drawing operations.  A thread would still block the isobar MIDI clock
thread via GIL contention.  A subprocess has its own independent GIL, so
Cairo renders there without affecting timing in the main process at all.

Data flow
─────────
  Main loop collects a RecordingContext command list (microseconds, shadow
  Cairo only) and calls DisplayProcess.submit().

  DisplayProcess replays the commands on a real cairo.Context in the worker
  process, converts the surface to a numpy frame, and puts it in a response
  queue.

  The main loop calls DisplayProcess.get_frame() each iteration.  If a
  frame is ready it calls push.display.display_frame() — USB I/O, which
  already releases the GIL, so this is safe.

  Queue sizes are capped at 2 so we never buffer more than one pending
  render; extra submissions or frames are silently dropped (display lag of
  one frame is imperceptible; MIDI timing is what matters).
"""

from __future__ import annotations

import multiprocessing
import queue as _queue
import traceback
from typing import Optional

import numpy

# Display dimensions are Push 2 hardware constants — importing only
# push2_python.constants avoids triggering USB/MIDI device initialisation.
_W = 960   # push2_python.constants.DISPLAY_LINE_PIXELS
_H = 160   # push2_python.constants.DISPLAY_N_LINES


# ---------------------------------------------------------------------------
# Worker — runs in the child process
# ---------------------------------------------------------------------------

def _replay(ctx: "cairo.Context", commands: list[tuple]) -> None:  # type: ignore[name-defined]
    """Replay a RecordingContext command list on a real cairo.Context."""
    for cmd in commands:
        op = cmd[0]
        args = cmd[1:]
        if op == "save":
            ctx.save()
        elif op == "restore":
            ctx.restore()
        elif op == "set_source_rgb":
            ctx.set_source_rgb(*args)
        elif op == "set_source_rgba":
            ctx.set_source_rgba(*args)
        elif op == "select_font_face":
            ctx.select_font_face(*args)
        elif op == "set_font_size":
            ctx.set_font_size(*args)
        elif op == "show_text":
            ctx.show_text(*args)
        elif op == "move_to":
            ctx.move_to(*args)
        elif op == "line_to":
            ctx.line_to(*args)
        elif op == "arc":
            ctx.arc(*args)
        elif op == "rectangle":
            ctx.rectangle(*args)
        elif op == "close_path":
            ctx.close_path()
        elif op == "fill":
            ctx.fill()
        elif op == "fill_preserve":
            ctx.fill_preserve()
        elif op == "stroke":
            ctx.stroke()
        elif op == "paint":
            ctx.paint()
        elif op == "set_line_width":
            ctx.set_line_width(*args)


def _worker(
    command_queue: multiprocessing.Queue,
    frame_queue: multiprocessing.Queue,
) -> None:
    """Entry point for the display worker process.

    Loops forever: receives a command list, renders it with Cairo, and
    puts the resulting numpy frame in frame_queue.  Sends None to
    frame_queue on shutdown so the main process can detect clean exit.
    """
    import cairo
    import numpy as np

    while True:
        try:
            item = command_queue.get()
            if item is None:  # shutdown sentinel
                break

            surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, _W, _H)
            ctx = cairo.Context(surface)
            _replay(ctx, item)

            buf = surface.get_data()
            # .copy() detaches from the surface buffer so it can be pickled safely.
            frame = np.ndarray(shape=(_H, _W), dtype=np.uint16, buffer=buf).transpose().copy()

            try:
                frame_queue.put_nowait(frame)
            except _queue.Full:
                # Main loop is slower than rendering; drop the oldest frame.
                pass

        except Exception:
            traceback.print_exc()


# ---------------------------------------------------------------------------
# Public interface — used by the main process
# ---------------------------------------------------------------------------

class DisplayProcess:
    """Manages the Cairo rendering subprocess and its I/O queues."""

    def __init__(self) -> None:
        self._command_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=2)
        self._frame_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=2)
        self._process: Optional[multiprocessing.Process] = None

    def start(self) -> None:
        self._process = multiprocessing.Process(
            target=_worker,
            args=(self._command_queue, self._frame_queue),
            daemon=True,
            name="CairoDisplayWorker",
        )
        self._process.start()

    def stop(self) -> None:
        if self._process and self._process.is_alive():
            try:
                self._command_queue.put_nowait(None)  # shutdown sentinel
            except _queue.Full:
                pass
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.terminate()

    def submit(self, commands: list[tuple]) -> None:
        """Non-blocking: hand a command list to the worker.  Drops if busy."""
        try:
            self._command_queue.put_nowait(commands)
        except _queue.Full:
            pass

    def get_frame(self) -> Optional[numpy.ndarray]:
        """Non-blocking: return the latest rendered frame, or None if not ready yet."""
        try:
            return self._frame_queue.get_nowait()
        except _queue.Empty:
            return None
