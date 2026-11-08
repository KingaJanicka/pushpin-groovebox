from __future__ import annotations

import logging
import os
from functools import partial
from typing import Any
import engine
import mido
import time
import isobar as iso
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
import definitions
from modes.osc_device import OSCDevice
from cc_client import MidiCCClient
from modes.device_definitions import load_device_definitions
from modes.mod_matrix_device import ModMatrixDevice
from modes.audio_in_device import AudioInDevice
from definitions import PyshaMode
import asyncio
logger = logging.getLogger("osc_instrument")
# logger.setLevel(level=logging.DEBUG)
from time import sleep

# Surge's patch commands: always for the track's Surge, whichever engine is
# playing, so a track that starts on mono2k still gets its Surge preset loaded.
SURGE_ONLY_ADDRESS_PREFIXES = ("/patch/",)


class Voice:
    """One synth engine on a track: the engine, its device pages, the slots
    that pick which pages show, and how the pages reach the synth (``osc``:
    client, server, dispatcher) and which MIDI port plays it."""

    def __init__(self, name: str, engine_: Any, osc: dict[str, Any], midi_out_device: Any) -> None:
        self.name = name
        self.engine = engine_
        self.osc = osc
        self.midi_out_device = midi_out_device
        self.slots: list[dict[str, Any] | None] = engine_.initial_slots()
        self.devices: list[list[Any]] = [[] for _ in range(16)]
        self.devices_modulation: list[Any] = []
        # Its device pages' init messages have been sent (on its first use)
        self.initialized = False

    @property
    def label(self) -> str:
        return engine.ENGINE_LABELS.get(self.name, self.name)


class Instrument(PyshaMode):
    """A pushpin track. It owns a Voice per available engine (Surge XT, and
    mono2k when m2k-jack is built) and plays one of them at a time: the
    active voice's engine, device pages, slots, OSC/CC client and MIDI port
    are this instrument's ``engine``, ``devices``, ``slots``, ``osc`` and
    ``midi_out_device``. Both engines run all the time and both are routed
    through the volume node; the inactive one gets no notes, so it is silent.
    """
    timeline = None

    def __init__(
        self,
        instrument_short_name,
        instrument_definition,
        device_definitions,
        get_current_instrument_color_helper,
        app,
        initial_engine=None,
        m2k_device_definitions=None,
        **kwargs
    ):
        """``device_definitions`` are the Surge voice's pages. ``initial_engine``
        picks the voice to start on (else the definition's "engine", else
        Surge); ``m2k_device_definitions`` default to engines/m2k/definitions."""
        self.app = app
        self.transports = []
        self.instrument_nodes = []
        self.instrument_ports = []
        self.instrument_global_volume = 1.0
        self.name = instrument_short_name
        self.definition = instrument_definition
        self.osc_in_port = instrument_definition.get("osc_in_port", None)
        self.osc_out_port = instrument_definition.get("osc_out_port", None)
        self.log_in = logger.getChild(f"in-{self.osc_in_port}")
        self.log_out = logger.getChild(f"out-{self.osc_out_port}")
        self.get_color = get_current_instrument_color_helper
        self.midi_channel = instrument_definition.get("midi_channel", 0)

        # this is vestigal and I think only has anything to do with external midi being sent
        # TODO remove and replace with Isobar midi in????
        self.midi_in_name = f'{instrument_definition["instrument_short_name"]}'
        self.midi_out_name = f'{instrument_definition["instrument_short_name"]}'

        # The port Surge listens to (and the global clock goes to)
        self.surge_midi_out_device = iso.MidiOutputDevice(
            device_name=self.midi_out_name, send_clock=True, virtual=True
        )

        midi_out_idx = [self.midi_in_name in output for output in iso.get_midi_input_names()].index(
            True
        )

        self.timeline = iso.Timeline(
            self.app.tempo,
            output_device=self.surge_midi_out_device
        )

        print("MIDI", midi_out_idx, mido.get_input_names()[midi_out_idx])  # type: ignore[attr-defined]

        self.voices: dict[str, Voice] = {}
        surge_engine = engine.SurgeXTEngine(
            app, midi_device_idx=midi_out_idx, instrument_definition=instrument_definition
        )
        self.voices[engine.DEFAULT_ENGINE] = self._build_voice(
            engine.DEFAULT_ENGINE, surge_engine, device_definitions, self.surge_midi_out_device
        )

        m2k_voice = self._build_m2k_voice(instrument_definition, midi_out_idx, m2k_device_definitions)
        if m2k_voice is not None:
            self.voices[engine.MONO2K_ENGINE] = m2k_voice

        wanted = initial_engine or instrument_definition.get("engine", engine.DEFAULT_ENGINE)
        if wanted not in self.voices:
            if wanted != engine.DEFAULT_ENGINE:
                logger.warning("%s: engine %r isn't available; starting on Surge XT", self.name, wanted)
            wanted = engine.DEFAULT_ENGINE
        self.active_engine_name: str = wanted

        self.current_devices = []
        for voice in self.voices.values():
            print(
                "Loaded {0} {1} devices for instrument {2}".format(
                    sum([len(slot) for slot in voice.devices]), voice.label, self.name,
                )
            )
        self.update_current_devices()

    # ------------------------------------------------------------------ voices

    def _build_voice(self, name, engine_, device_definitions, midi_out_device) -> Voice:
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(lambda *message: self.log_in.debug(message))
        client = None
        if engine_.control_transport == "midi-cc":
            # Device pages, p-locks and pads send "/cc/<n>" and "/mnote" through
            # this stand-in for the OSC client; it also echoes values as Surge does.
            client = MidiCCClient(
                midi_out_device,
                dispatcher,
                channel=self.midi_channel,
                nrpn=getattr(engine_, "nrpn", False),
                plain_ccs=getattr(engine_, "PLAIN_CCS", ()),
            )
        elif self.osc_in_port:
            client = SimpleUDPClient("127.0.0.1", self.osc_in_port)

        voice = Voice(name, engine_, {"client": client, "server": None, "dispatcher": dispatcher}, midi_out_device)
        for slot in voice.slots:
            if slot:
                dispatcher.map(slot["address"], partial(self._voice_slot_state, voice))

        for device_name in device_definitions:
            if device_name == "mod_matrix":
                device = ModMatrixDevice(
                    voice.osc,
                    get_color=self.get_color,
                    osc_in_port=self.osc_in_port,
                    osc_out_port=self.osc_out_port,
                    app=self.app,
                    engine=engine_
                )
            elif device_name == "audio_1" or device_name == "audio_2":
                device = AudioInDevice(
                    device_definitions[device_name],
                    voice.osc,
                    get_color=self.get_color,
                    osc_in_port=self.osc_in_port,
                    osc_out_port=self.osc_out_port,
                    app=self.app,
                    engine=engine_
                )
            else:
                device = OSCDevice(
                    device_definitions[device_name],
                    voice.osc,
                    get_color=self.get_color,
                    osc_in_port=self.osc_in_port,
                    osc_out_port=self.osc_out_port,
                    app=self.app,
                    engine=engine_
                )
            slot_idx = device_definitions[device_name]["slot"]
            voice.devices[slot_idx].append(device)

        self._resolve_dynamic_labels(voice)

        # gets all the modulation devices
        for slot_idx, slot_devices in enumerate(voice.devices):
            for device in slot_devices:
                if 8 <= slot_idx <= 15:
                    voice.devices_modulation.append(device)
        return voice

    def _resolve_dynamic_labels(self, voice: Voice) -> None:
        """Menu items naming another device's control (label_from) get their
        label from whatever that slot shows now, as the mod matrix does."""
        def items_of(control):
            for item in getattr(control, "items", []) or []:
                yield item
            for group in getattr(control, "groups", []) or []:
                for c in group.controls:
                    yield from items_of(c)

        for slot_devices in voice.devices:
            for device in slot_devices:
                for control in getattr(device, "controls", []):
                    for item in items_of(control):
                        source = getattr(item, "label_from", None)
                        if source:
                            item.label_func = partial(
                                self._slot_control_label, voice, int(source["slot"]), int(source["control"]))

    def _slot_control_label(self, voice: Voice, slot_idx: int, control_idx: int) -> str | None:
        """The label of the control_idx-th control of the device slot_idx shows."""
        slot = voice.slots[slot_idx] if slot_idx < len(voice.slots) else None
        for device in voice.devices[slot_idx]:
            if slot is not None and not any(
                init["address"] == slot["address"] and int(init["value"]) == float(slot["value"])
                for init in device.init
            ):
                continue
            controls = getattr(device, "controls", [])
            if control_idx < len(controls):
                control = controls[control_idx]
                # a menu's label is its selected item; its name is its menu_label (WAVE, not SIN)
                return getattr(control, "menu_label", None) or getattr(control, "label", None) or "-"
            return "-"
        return None

    def _build_m2k_voice(self, instrument_definition, midi_out_idx, m2k_device_definitions) -> Voice | None:
        """The track's mono2k voice, or None when m2k-jack isn't built or the
        track has no mono2k track (instrument_index outside 0-7)."""
        if not engine.m2k_available():
            return None
        try:
            m2k_engine = engine.M2KEngine(
                self.app, midi_device_idx=midi_out_idx, instrument_definition=instrument_definition
            )
        except (AssertionError, ValueError, TypeError) as e:
            logger.warning("%s: no mono2k voice (%s)", self.name, e)
            return None
        if m2k_device_definitions is None:
            m2k_device_definitions = load_device_definitions(definitions.M2K_DEFINITION_FOLDER)
        m2k_port = iso.MidiOutputDevice(device_name=m2k_engine.midi_port_name, send_clock=False, virtual=True)
        return self._build_voice(engine.MONO2K_ENGINE, m2k_engine, m2k_device_definitions, m2k_port)

    @property
    def active_voice(self) -> Voice:
        return self.voices[self.active_engine_name]

    @property
    def engine(self) -> Any:
        return self.active_voice.engine

    @property
    def osc(self) -> dict[str, Any]:
        return self.active_voice.osc

    @property
    def slots(self) -> list[dict[str, Any] | None]:
        return self.active_voice.slots

    @property
    def devices(self) -> list[list[Any]]:
        return self.active_voice.devices

    @property
    def devices_modulation(self) -> list[Any]:
        return self.active_voice.devices_modulation

    @property
    def midi_out_device(self) -> Any:
        """The port the active engine listens to: the sequencer plays this."""
        return self.active_voice.midi_out_device

    @property
    def midi_in_device(self) -> Any:
        return self.active_voice.midi_out_device

    @property
    def plays_surge(self) -> bool:
        return self.active_engine_name == engine.DEFAULT_ENGINE

    def available_engines(self) -> list[str]:
        return list(self.voices)

    def set_active_engine(self, name: str) -> bool:
        """Play this track on another engine. Returns False when it already is
        or the engine isn't available. The old engine's notes are stopped, the
        new one's pages are initialised on its first use, and the track's
        p-locks are cleared (they are stored by page position, which means
        different parameters on another engine)."""
        if name == self.active_engine_name or name not in self.voices:
            return False
        old = self.active_voice
        self._all_notes_off(old)
        self.active_engine_name = name
        self.update_current_devices()
        new = self.active_voice
        if not new.initialized:
            self.init_devices_sync()
        else:
            # What changed while it wasn't playing (e.g. a Surge preset loaded
            # meanwhile) shows on its pages: Surge answers, the CC client replays
            self.query_slots()
            self.update_current_devices()
            self.query_all_controls()
        sequencers = getattr(getattr(self.app, "metro_sequencer_mode", None), "instrument_sequencers", None)
        if isinstance(sequencers, dict) and self.name in sequencers:
            sequencers[self.name].clear_all_locks()
        return True

    def _all_notes_off(self, voice: Voice) -> None:
        """All notes off (CC 123) on the voice's port: a held pad or a sequenced
        note must not hang on the engine that no longer gets the note-off."""
        try:
            voice.midi_out_device.control(123, 0, max(0, min(int(self.midi_channel), 15)))
        except Exception:
            logger.exception("%s: all notes off failed", self.name)

    async def configure_pipewire(self) -> None:
        """Route every voice's engine through the volume node. Surge's failing is
        as fatal as it always was; mono2k's failing drops the mono2k voice."""
        for name, voice in list(self.voices.items()):
            if name == engine.DEFAULT_ENGINE:
                await voice.engine.configure_pipewire()
                continue
            try:
                await voice.engine.configure_pipewire()
            except Exception:
                logger.exception("%s: routing the %s voice failed; dropping it", self.name, voice.label)
                if self.active_engine_name == name:
                    self.set_active_engine(engine.DEFAULT_ENGINE)
                del self.voices[name]

    # ------------------------------------------------------- slots and devices

    def update_current_devices(self):
        updated_devices = []
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if slot_idx in self.engine.always_shown_slots:
                    updated_devices.append(device)
                else:
                    slot = self.slots[slot_idx]
                    if slot is None:
                        continue
                    for init in device.init:
                        if init["address"] == slot["address"] and int(init["value"]) == float(slot["value"]):
                            updated_devices.append(device)
        self.current_devices = updated_devices
        return

    def _voice_slot_state(self, voice: Voice, *resp):
        """A slot address answered for one voice (Surge's echo, or the CC
        client's): update that voice's slots, active or not."""
        address, value, *rest = resp
        slots = voice.slots
        for slot in slots:
            if slot and slot["address"] == address:

                # This compares new value with current value and fires a selected/disselected call
                if 'param/a/osc/' in slot["address"] and value == 4 and slot["value"] != 4:
                    engine_ = voice.engine
                    for external_instrument in self.app.external_instruments:
                        self.app.queue.append(external_instrument.engine.configure_pipewire())
                    if engine_.puredata_process_id == None:
                        self.app.queue.append(engine_.start_pd_node())

                if 'param/a/osc/' in slot["address"] and value != 4 and slot["value"] == 4:
                    engine_ = voice.engine

                    # This if statemant is so that we don't kill a duplex node if
                    # another instance of audio-in device is active
                    if slots[0]["value"] != 4 or slots[1]["value"] != 4:
                        self.app.queue.append(engine_.kill_pd_node())

                if float(slot["value"]) != float(value):
                    slot["value"] = float(value)
                    break
        if voice is self.active_voice:
            self.update_current_devices()

    def set_slot_state(self, *resp):
        self._voice_slot_state(self.active_voice, *resp)

    async def init_devices(self):
        self.active_voice.initialized = True
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if slot_idx in self.engine.always_shown_slots:
                    await device.select()
                else:
                    slot = self.slots[slot_idx]
                    if slot is None:
                        continue
                    for init in device.init:
                        if init["address"] == slot["address"] and int(
                            init["value"]
                        ) == float(slot["value"]):
                            await device.select()

    def init_devices_sync(self):
        self.active_voice.initialized = True
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if slot_idx in self.engine.always_shown_slots:
                    device.select_sync()
                else:
                    slot = self.slots[slot_idx]
                    if slot is None:
                        continue
                    for init in device.init:
                        if init["address"] == slot["address"] and int(
                            init["value"]
                        ) == float(slot["value"]):
                            device.select_sync()

    def query_devices(self):
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if slot_idx in self.engine.always_shown_slots:
                    device.query_visible_controls()
                else:
                    slot = self.slots[slot_idx]
                    if slot is None:
                        continue
                    for init in device.init:
                        if init["address"] == slot["address"] and int(
                            init["value"]
                        ) == float(slot["value"]):
                            device.query_visible_controls()

    def query_all_controls(self):
        for slot_idx, slot_devices in enumerate(self.devices):
            for device in slot_devices:
                if slot_idx in self.engine.always_shown_slots:
                    device.query_all_controls()
                else:
                    slot = self.slots[slot_idx]
                    if slot is None:
                        continue
                    for init in device.init:
                        if init["address"] == slot["address"] and int(
                            init["value"]
                        ) == float(slot["value"]):
                            device.query_all_controls()

    """
    Initialise OSC servers and add to transport array so they can be gracefully closed
    """

    async def start(self, loop):
        if self.osc_out_port:
            # Surge answers on osc_out_port, into the Surge voice's dispatcher
            server = AsyncIOOSCUDPServer(
                ("127.0.0.1", self.osc_out_port), self.voices[engine.DEFAULT_ENGINE].osc["dispatcher"], loop
            )

            transport, protocol = (
                await server.create_serve_endpoint()
            )  # Create datagram endpoint and start serving

            self.transports.append(transport)
            self.log_out.debug(f"Receiving OSC on port {self.osc_out_port}")
            self.query_slots()
            self.query_devices()

            # This starts the Surge-XT instances (and the shared m2k-jack)
            for voice in self.voices.values():
                asyncio.create_task(voice.engine.start())

    def query_all_params(self):
        # TODO: this is broken
        # # print(self.devices)
        # for device in self.devices:
        #     print(device.label)
            # device.query_all()
        client = self.osc["client"]
        if client:
            # print(f"Querying all_params on {self.name}")
            client.send_message("/q/all_params", None)

    def query_slots(self):
        """Ask every voice which device each slot shows (Surge answers over
        OSC; the CC client from what it last sent)."""
        for voice in self.voices.values():
            client = voice.osc["client"]
            if client:
                for slot in voice.slots:
                    if slot:
                        # print(f'querrying slot /q{slot["address"]}')
                        client.send_message(f'/q{slot["address"]}', None)

    """
    Close transports on ctrl+c

    @TODO is this still needed?
    """

    def close_transports(self):
        # print("Closing transports")
        # for transport in self.transports:
        #     transport.close()
        pass

    def client_for(self, address: str) -> Any:
        """The client a message goes to: the active voice's, except Surge's patch
        commands, which always go to the track's Surge."""
        if address.startswith(SURGE_ONLY_ADDRESS_PREFIXES):
            return self.voices[engine.DEFAULT_ENGINE].osc["client"]
        return self.osc["client"]

    def send_message(self, address, *args):
        client = self.client_for(address)
        if client:
            return client.send_message(address, *args)
