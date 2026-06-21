"""Tests for OSCMode - device/slot navigation.

initialize() reads instrument definition JSON off disk and builds Instrument
objects, so it is patched out. A light fake instrument exercises the device and
slot navigation logic. Several methods reach back through ``self.app.osc_mode``,
so the fixture points that at the mode under test.
"""

from __future__ import annotations

from typing import Any
import pytest

from modes.osc_mode import OSCMode


class FakeDevice:
    def __init__(self, label, slot):
        self.label = label
        self.slot = slot
        self.page = None

    def set_page(self, page):
        self.page = page


@pytest.fixture
def fake_instrument():
    osc = FakeDevice("Osc", slot=0)
    filt = FakeDevice("Filter", slot=0)
    amp = FakeDevice("Amp", slot=1)
    inst: Any = type("Inst", (), {})()
    inst.current_devices = [osc, filt, amp]
    inst.devices = [[osc, filt], [amp]]
    inst.devices_modulation = [amp]
    return inst


@pytest.fixture
def osc_mode(app, mocker, fake_instrument):
    mocker.patch.object(OSCMode, "initialize")
    OSCMode.current_device_index_and_page = [0, 0]
    OSCMode.instrument_page = 0
    OSCMode.state = {}
    mode = OSCMode(app, settings=None)
    app.instruments = {"INST1": fake_instrument}
    # Several methods call back through self.app.osc_mode.
    app.osc_mode = mode
    return mode


def test_helpers_delegate(osc_mode):
    assert osc_mode.get_current_instrument_short_name_helper() == "INST1"
    assert osc_mode.get_all_distinct_instrument_short_names_helper() == [
        "INST1",
        "INST2",
    ]


def test_get_current_instrument(osc_mode, fake_instrument):
    assert osc_mode.get_current_instrument() is fake_instrument


def test_page_devices_switch_on_instrument_page(osc_mode, fake_instrument):
    osc_mode.instrument_page = 0
    assert osc_mode.get_current_instrument_page_devices() == fake_instrument.current_devices
    osc_mode.instrument_page = 1
    assert (
        osc_mode.get_current_instrument_page_devices()
        == fake_instrument.devices_modulation
    )


def test_current_device_and_page(osc_mode, fake_instrument):
    osc_mode.current_device_index_and_page = [0, 0]
    device, page = osc_mode.get_current_instrument_device_and_page()
    assert device is fake_instrument.current_devices[0]
    assert page == 0


def test_get_current_slot_devices_sorted_by_label(osc_mode):
    # Current device is in slot 0; that slot holds Osc + Filter, returned sorted.
    devices = osc_mode.get_current_slot_devices()
    assert [d.label for d in devices] == ["Filter", "Osc"]


def test_update_current_device_page_sets_index_and_page(osc_mode, fake_instrument, app):
    osc_mode.current_device_index_and_page = [0, 0]
    osc_mode.update_current_device_page(new_device=1, new_page=2)
    assert osc_mode.current_device_index_and_page == [1, 2]
    # The newly-selected device gets its page set.
    assert fake_instrument.current_devices[1].page == 2
    assert app.buttons_need_update is True


def test_new_instrument_selected_is_noop(osc_mode):
    assert osc_mode.new_instrument_selected() is None
