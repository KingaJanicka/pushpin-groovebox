"""definitions.track_label: pushpin's tracks as the Push shows them, Trk 1-8, whatever their names (Pushpin 0-7)."""
import pytest

import definitions


@pytest.mark.parametrize("name, shown", [("Pushpin 0", "Trk 1"), ("Pushpin 2", "Trk 3"), ("Pushpin 7", "Trk 8")])
def test_pushpin_tracks_show_as_trk_1_to_8(name, shown):
    assert definitions.track_label(name) == shown


@pytest.mark.parametrize("name", ["Overwitch", "Pushpin", "Pushpin x", "-"])
def test_anything_else_shows_as_it_is(name):
    assert definitions.track_label(name) == name
