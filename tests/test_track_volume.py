"""Track volume: the Swing encoder's post-synth fader (``PyshaApp.volumes``,
dB-tapered on its way to the volume node) and the Master encoder
(``Instrument.set_global_volume``: Surge's global volume, and a scale on a
mono2k sound's own LEVL)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import push2_python.constants as B
import pytest
from pythonosc.dispatcher import Dispatcher

import engine
import m2k_state
from app import PyshaApp
from cc_client import MidiCCClient
from modes.osc_mode import OSCMode
from tests.test_cc_client import make_instrument
from tests.test_m2k_state import nrpns
from utilities.volume_taper import fader_to_gain


# ------------------------------------------------------- CC client transform


@pytest.fixture
def midi_out():
    return MagicMock()


@pytest.fixture
def client(midi_out):
    return MidiCCClient(midi_out, Dispatcher(), channel=0, nrpn=True, plain_ccs={7})


def test_transform_changes_what_is_sent_not_what_is_cached(client, midi_out):
    client.set_transform("/cc/7", lambda v: v / 2)
    client.send_message("/cc/7", 100)
    midi_out.control.assert_called_once_with(7, 50, 0)
    assert client.values["/cc/7"] == 100.0


def test_setting_a_transform_resends_the_last_value(client, midi_out):
    client.send_message("/cc/7", 100)
    midi_out.reset_mock()
    client.set_transform("/cc/7", lambda v: v / 4)
    midi_out.control.assert_called_once_with(7, 25, 0)
    midi_out.reset_mock()
    client.set_transform("/cc/7", None)
    midi_out.control.assert_called_once_with(7, 100, 0)


def test_transform_before_any_value_sends_nothing(client, midi_out):
    client.set_transform("/cc/7", lambda v: 0)
    midi_out.control.assert_not_called()


def test_transform_needs_a_cc_address(client):
    with pytest.raises(ValueError):
        client.set_transform("/m2k/param/3", lambda v: v)


# ------------------------------------------------------------ LEVL scaling


def test_scaled_level_follows_monos_square_law():
    assert m2k_state.scaled_level(127, 1.0) == pytest.approx(127)
    assert m2k_state.scaled_level(127, 0.25) == pytest.approx(63.5)
    assert m2k_state.scaled_level(100, 0.0) == 0.0
    assert m2k_state.scaled_level(200, 2.0) == pytest.approx(127)


# ------------------------------------------------- Instrument Master volume


@pytest.fixture
def m2k_instrument(app):
    instrument, ports = make_instrument(app)
    surge_client = MagicMock()
    instrument.voices[engine.DEFAULT_ENGINE].osc["client"] = surge_client
    m2k_out = ports["Pushpin 2 m2k"]
    instrument.osc["client"].send_message(m2k_state.LEVEL_ADDRESS, 127)
    m2k_out.reset_mock()
    return instrument, surge_client, m2k_out


def sent_levels(midi_out):
    """LEVL values sent on a mocked m2k port (CC 7 goes as NRPN 0:7)."""
    return [whole + fraction / 128 for msb, lsb, whole, fraction in nrpns(midi_out) if (msb, lsb) == (0, 7)]


def level(levl, position):
    return m2k_state.scaled_level(levl, fader_to_gain(position))


def test_master_scales_m2k_level_on_the_db_taper(m2k_instrument):
    instrument, _, m2k_out = m2k_instrument
    instrument.set_global_volume(0.5)
    assert sent_levels(m2k_out) == pytest.approx([level(127, 0.5)], abs=1 / 128)
    # the sound keeps its own LEVL: pages and saved sounds don't see the Master
    assert instrument.osc["client"].values[m2k_state.LEVEL_ADDRESS] == 127.0


def test_master_survives_a_sound_setting_its_level(m2k_instrument):
    instrument, _, m2k_out = m2k_instrument
    instrument.set_global_volume(0.5)
    m2k_out.reset_mock()
    instrument.osc["client"].send_message(m2k_state.LEVEL_ADDRESS, 100)
    assert sent_levels(m2k_out) == pytest.approx([level(100, 0.5)], abs=1 / 128)


def test_master_at_full_sends_the_sounds_level(m2k_instrument):
    instrument, _, m2k_out = m2k_instrument
    instrument.set_global_volume(0.5)
    m2k_out.reset_mock()
    instrument.set_global_volume(1.0)
    assert sent_levels(m2k_out) == [127]
    assert instrument.osc["client"].transforms == {}


def test_master_at_zero_silences_m2k(m2k_instrument):
    instrument, _, m2k_out = m2k_instrument
    instrument.set_global_volume(0.0)
    assert sent_levels(m2k_out) == [0]


def test_master_also_sets_surge_global_volume(m2k_instrument):
    instrument, surge_client, _ = m2k_instrument
    instrument.set_global_volume(1.7)
    surge_client.send_message.assert_called_once_with("/param/global/volume", 1.0)
    assert instrument.instrument_global_volume == 1.0


def test_master_without_m2k_voice_only_touches_surge(app):
    instrument, _ = make_instrument(app, m2k_built=False)
    surge_client = MagicMock()
    instrument.voices[engine.DEFAULT_ENGINE].osc["client"] = surge_client
    instrument.set_global_volume(0.3)
    surge_client.send_message.assert_called_once_with("/param/global/volume", 0.3)


# ------------------------------------------------------------ the encoders


def test_master_encoder_steps_and_clamps(app, mocker):
    mocker.patch.object(OSCMode, "initialize")
    mode = OSCMode(app, settings=None)
    instrument = MagicMock(instrument_global_volume=0.995)
    app.instruments = {"INST1": instrument}
    mode.on_encoder_rotated(B.ENCODER_MASTER_ENCODER, 3)
    instrument.set_global_volume.assert_called_once_with(1.0)


def test_swing_encoder_moves_both_channels_of_the_track():
    volumes = [0.5] * 16
    fake = SimpleNamespace(volumes=volumes, set_main_volumes=MagicMock())
    PyshaApp.adjust_track_volume(fake, SimpleNamespace(osc_in_port=1031), -2)
    assert volumes[2] == volumes[3] == pytest.approx(0.48)
    assert volumes[0] == 0.5
    fake.set_main_volumes.assert_called_once()


def test_main_volumes_send_tapered_gain():
    client = MagicMock()
    fake = SimpleNamespace(instruments=[0], volumes=[0.5, 0.5], volume_node_osc_client=client)
    PyshaApp.set_main_volumes(fake)
    gain = fader_to_gain(0.5)
    assert [c.args for c in client.send_message.call_args_list] == [("/vol_0", gain), ("/vol_1", gain)]
