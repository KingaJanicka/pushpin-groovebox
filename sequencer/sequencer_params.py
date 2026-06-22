from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SequencerParams:
    """Immutable snapshot of UI-owned state consumed by the sequencer.

    The asyncio event loop writes a fresh instance each frame via
    MetroSequencerMode.refresh_sequencer_params().  The MIDI clock thread
    reads self.params once per tick and holds the reference for the
    duration of that tick — CPython reference assignment is atomic under
    the GIL, so no explicit lock is required.

    Keeping this frozen (immutable) means the MIDI clock thread can never
    accidentally write back through it.
    """

    sequencer_is_playing: bool = False
    gate_track_active: bool = True

    # Gate length in beats (controls[0].value)
    gate_len: float = 1.0

    # Sequencer time subdivision (controls[4] menu value)
    seq_time_scale: int = 1

    # Number of active steps in this instrument's pattern (controls[5])
    pattern_len: int = 16

    # Global pattern time subdivision (controls[6])
    main_seq_time_scale: int = 1

    # Global pattern length in steps (controls[7])
    main_pattern_len: int = 64
