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
  process, writes the rendered numpy frame into a shared-memory block, then
  puts a lightweight True sentinel into frame_ready_queue.

  The main loop calls DisplayProcess.get_frame() each iteration.  If a ready
  signal is waiting it copies the frame from shared memory (no pickling) and
  calls push.display.display_frame() — USB I/O, which releases the GIL.

  Shared-memory layout: one slot, 960 × 160 × uint16 = 307 200 bytes.
  The worker owns the slot while rendering; the main process copies it in
  microseconds immediately on signal.  At 30 fps with ~10–30 ms render times
  the race window between successive writes is negligible.  A future
  double-buffer variant would eliminate it entirely.

  Command and signal queues are capped at 2 so we never buffer more than one
  pending render; extra submissions or frames are silently dropped.
"""

from __future__ import annotations

import multiprocessing
import multiprocessing.shared_memory as _shm_mod
import queue as _queue
import traceback
from typing import Optional

import numpy

# Display dimensions are Push 2 hardware constants — importing only
# push2_python.constants avoids triggering USB/MIDI device initialisation.
_W = 960   # push2_python.constants.DISPLAY_LINE_PIXELS
_H = 160   # push2_python.constants.DISPLAY_N_LINES
_FRAME_BYTES = _W * _H * 2  # one uint16 per pixel


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
    frame_ready_queue: multiprocessing.Queue,
    shm_name: str,
) -> None:
    """Entry point for the display worker process.

    Loops forever: receives a command list, renders it with Cairo, writes the
    resulting numpy frame into the named shared-memory block, and signals the
    main process via frame_ready_queue.  Sends None to frame_ready_queue on
    shutdown so the main process can detect a clean exit.
    """
    import cairo
    import numpy as np
    from multiprocessing.shared_memory import SharedMemory

    shm = SharedMemory(name=shm_name)
    # View into shared memory — shape matches what get_frame() expects.
    frame_buf = np.ndarray(shape=(_W, _H), dtype=np.uint16, buffer=shm.buf)

    try:
        while True:
            item = command_queue.get()
            if item is None:  # shutdown sentinel
                break

            surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, _W, _H)
            ctx = cairo.Context(surface)
            _replay(ctx, item)

            buf = surface.get_data()
            # Transpose from (H, W) surface layout to (W, H) Push 2 frame layout
            # and write directly into shared memory (no extra copy).
            frame_buf[:] = np.ndarray(shape=(_H, _W), dtype=np.uint16, buffer=buf).transpose()

            try:
                frame_ready_queue.put_nowait(True)
            except _queue.Full:
                # Main loop is slower than rendering; drop the signal for this frame.
                pass

    except Exception:
        traceback.print_exc()
    finally:
        shm.close()


# ---------------------------------------------------------------------------
# Public interface — used by the main process
# ---------------------------------------------------------------------------

class DisplayProcess:
    """Manages the Cairo rendering subprocess and its shared-memory I/O."""

    def __init__(self) -> None:
        self._command_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=2)
        self._frame_ready: multiprocessing.Queue = multiprocessing.Queue(maxsize=2)
        # Shared memory block — worker writes frames here; main reads via _frame_view.
        self._shm = _shm_mod.SharedMemory(create=True, size=_FRAME_BYTES)
        self._frame_view = numpy.ndarray(
            shape=(_W, _H), dtype=numpy.uint16, buffer=self._shm.buf
        )
        self._process: Optional[multiprocessing.Process] = None

    def start(self) -> None:
        self._process = multiprocessing.Process(
            target=_worker,
            args=(self._command_queue, self._frame_ready, self._shm.name),
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
        # Release the shared-memory segment.  close() detaches; unlink() frees
        # the POSIX shm object — only the creator (main process) should unlink.
        self._shm.close()
        self._shm.unlink()

    def submit(self, commands: list[tuple]) -> None:
        """Non-blocking: hand a command list to the worker.  Drops if busy."""
        try:
            self._command_queue.put_nowait(commands)
        except _queue.Full:
            pass

    def get_frame(self) -> Optional[numpy.ndarray]:
        """Non-blocking: return a copy of the latest rendered frame, or None."""
        try:
            self._frame_ready.get_nowait()
        except _queue.Empty:
            return None
        # Copy out of shared memory before the worker can write the next frame.
        return self._frame_view.copy()
