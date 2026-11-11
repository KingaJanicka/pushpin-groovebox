"""isobar's per-Track callback thread must not outlive its Track.

isobar 0.2.1 starts a ``threading.Thread`` in every ``Track.__init__`` that
loops on ``callback_queue.get()`` forever. The sequencers schedule one Track per
played note, so each note leaked a thread; after ~20 minutes of playing the app
hit systemd's TasksMax and every step failed with "can't start new thread"
(no sound). ``sequencer.isobar_threads`` makes those threads exit once their
Track is finished or removed from the timeline.

These tests drive a real isobar Timeline by hand (no clock thread, no MIDI).
"""

import threading
import time

import isobar as iso
from isobar.timelines.track import Track

import sequencer.isobar_threads as isobar_threads


def _timeline():
    return iso.Timeline(120, output_device=iso.DummyOutputDevice())


def _wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def _play_out(timeline, beats):
    for _ in range(int(beats / timeline.tick_duration) + 2):
        timeline.tick()


def test_fix_is_installed_on_import():
    assert Track._callback_thread is isobar_threads._callback_thread


def test_install_is_idempotent():
    isobar_threads.install()
    isobar_threads.install()
    assert Track._callback_thread is isobar_threads._callback_thread


def test_one_shot_note_tracks_do_not_leak_threads():
    timeline = _timeline()
    before = threading.active_count()

    # Same call the metro sequencer makes for every played step.
    for i in range(50):
        timeline.schedule({"note": 60 + i % 12, "gate": 0.25, "amplitude": 100}, count=1)
    assert threading.active_count() >= before + 50  # one thread per Track, as isobar does

    _play_out(timeline, beats=2)
    assert timeline.tracks == []  # every note played and its Track was removed

    assert _wait_until(lambda: threading.active_count() <= before), (
        "isobar Track callback threads outlived their finished Tracks: "
        f"{threading.active_count() - before} still running"
    )


def test_unscheduled_track_releases_its_thread():
    timeline = _timeline()
    before = threading.active_count()
    track = timeline.schedule({"note": 60, "duration": 1})  # endless, like the playhead
    assert threading.active_count() == before + 1

    timeline.unschedule(track)

    assert _wait_until(lambda: threading.active_count() <= before)


def test_live_track_keeps_its_thread_and_runs_callbacks():
    timeline = _timeline()
    seen = []
    timeline.on_event_callback = lambda event: seen.append(event)
    before = threading.active_count()
    timeline.schedule({"note": 60, "duration": 0.25})  # endless track, still scheduled

    # Longer than the idle check, so an over-eager exit would show up here.
    time.sleep(isobar_threads.IDLE_CHECK_SECONDS * 3)
    assert threading.active_count() == before + 1

    _play_out(timeline, beats=1)
    assert _wait_until(lambda: len(seen) >= 4)


def test_finished_track_with_callbacks_still_finishes():
    # is_finished waits for the callback queue to drain, so the thread has to
    # keep serving it until then rather than exiting first.
    timeline = _timeline()
    seen = []
    timeline.on_event_callback = lambda event: seen.append(event)
    before = threading.active_count()

    timeline.schedule({"note": 60, "gate": 0.25}, count=1)
    for _ in range(200):
        _play_out(timeline, beats=0.25)
        if not timeline.tracks:
            break

    assert timeline.tracks == []
    assert len(seen) == 1
    assert _wait_until(lambda: threading.active_count() <= before)
