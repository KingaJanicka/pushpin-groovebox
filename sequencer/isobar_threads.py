"""Stop isobar's per-Track callback threads from leaking.

isobar (0.2.1, and master as of 2026-11) starts a daemon thread in every
``Track.__init__`` that loops on ``callback_queue.get()`` forever, so the thread
outlives its Track. The sequencers schedule a one-shot Track for every played
note (``timeline.schedule({...}, count=1)``), so each note leaked one thread.
After ~20 minutes of playing, the app hit systemd's TasksMax (9254 on the Pi),
and from then on every step failed with ``RuntimeError: can't start new thread``.
No notes went out, so there was no sound.

The replacement loop below serves callbacks exactly as before. When it is idle,
it exits once its Track has finished or has been removed from the timeline.
Importing this module installs it. It must be imported before any Track is
created, because each thread binds ``_callback_thread`` when its Track is built.
"""

from __future__ import annotations

import logging
import queue

from isobar.timelines.track import Track

logger = logging.getLogger(__name__)

# How long an idle callback thread waits before checking whether its Track is done.
IDLE_CHECK_SECONDS = 0.25


def _callback_thread(self: Track) -> None:
    while True:
        try:
            callback = self.callback_queue.get(timeout=IDLE_CHECK_SECONDS)
        except queue.Empty:
            # The queue is drained, so a finished Track has nothing left to run.
            # A Track off the timeline (finished and removed, or unscheduled) will
            # never be ticked again, so nothing more can be queued for it.
            if self.is_finished or self not in self.timeline.tracks:
                return
            continue
        callback()


def install() -> None:
    """Patch isobar's Track to use the exiting callback loop (idempotent)."""
    if Track.__dict__.get("_callback_thread") is _callback_thread:
        return
    if not callable(Track.__dict__.get("_callback_thread")):
        logger.warning(
            "isobar Track has no _callback_thread; the thread-leak fix was not installed"
        )
        return
    Track._callback_thread = _callback_thread


install()
