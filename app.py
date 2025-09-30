import json
import os
import sys
import platform
import time
import traceback
import cairo
import definitions
import mido
import numpy
import push2_python
import asyncio
import logging
import jack
import isobar as iso
import re
from ratelimit import limits
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher

from engine import disconnectPipewireLink
from modes.melodic_mode import MelodicMode
from modes.instrument_selection_mode import InstrumentSelectionMode
from modes.rhythmic_mode import RhythmicMode
from modes.slice_notes_mode import SliceNotesMode
from modes.sequencer_mode import SequencerMode
from modes.metro_sequencer_mode import MetroSequencerMode
from modes.settings_mode import SettingsMode
from modes.main_controls_mode import MainControlsMode
from modes.midi_cc_mode import MIDICCMode
from modes.osc_mode import OSCMode
from modes.preset_selection_mode import PresetSelectionMode
from modes.trig_edit_mode import TrigEditMode
from modes.ddrm_tone_selector_mode import DDRMToneSelectorMode
from modes.menu_mode import MenuMode
from modes.mute_mode import MuteMode
from user_interface.display_utils import show_notification
from modes.external_instrument import ExternalInstrument
from definitions import DEFAULT_GLOBAL_TEMPO

logger = logging.getLogger("app.py")
# logging.basicConfig(level=logging.DEBUG)
# logging.getLogger().setLevel(level=logging.DEBUG)


class PyshaApp(object):
    # global state
    instruments = {}
    tempo = DEFAULT_GLOBAL_TEMPO
    # midi
    midi_out = None
    available_midi_out_device_names = []
    midi_out_channel = 0  # 0-15
    midi_out_tmp_device_idx = (
        None  # This is to store device names while rotating encoders
    )

    midi_in = None
    available_midi_in_device_names = []
    midi_in_channel = 0  # 0-15
    midi_in_tmp_device_idx = (
        None  # This is to store device names while rotating encoders
    )

    notes_midi_in = None  # MIDI input device only used to receive note messages and illuminate pads/keys
    notes_midi_in_tmp_device_idx = (
        None  # This is to store device names while rotating encoders
    )

    # push
    push = None
    use_push2_display = None
    target_frame_rate = None

    # frame rate measurements
    actual_frame_rate = 0
    current_frame_rate_measurement = 0
    current_frame_rate_measurement_second = 0

    # other state vars
    active_modes = []
    previously_active_mode_for_xor_group = {}
    pads_need_update = True
    buttons_need_update = True
    steps_held=[]

    # notifications
    notification_text = None
    notification_time = 0

    # fixing issue with 2 lumis and alternating channel pressure values
    last_cp_value_recevied = 0
    last_cp_value_recevied_time = 0

    # client = SimpleUDPClient("127.0.0.1", 1032)
    tasks = set()
    queue = []

    # Pipewire-related
    external_instruments = []
    pipewire = None
    volumes = [ 0.6,0.6,0.6,0.6,0.6,0.6,0.6,0.6,0.6,0.6,0.6,0.6,0.6,0.6,0.6,0.6]
    volume_client = None
    volume_node = None
    iso_midi_in = None
    global_timeline = None
    pwcli = None
    puredata_process_id = None
    puredata_client_id = None
    # Magic number is defined in the puradata patch
    volume_node_osc_address = 1058
    volume_node_osc_client = None
    volume_node_osc_server = None
    volume_node_osc = None
    log_in = None
    
    settings = None
    iso_midi_in_device_name = None
   
        
    def __init__(self):
        if os.path.exists("settings.json"):
            print("Loaded Settings ......")
            self.settings = json.load(open("settings.json"))
        else:
            self.settings = {}
        # Setup stuff for the volume node osc client
        dispatcher = Dispatcher()
        self.log_in = logger.getChild(f"in-{self.volume_node_osc_address}")
        dispatcher.set_default_handler(lambda *message: self.log_in.debug(message))
        self.volume_node_osc_client = SimpleUDPClient("127.0.0.1", int(self.volume_node_osc_address))
        self.volume_node_osc = {"client": self.volume_node_osc_client, "server": self.volume_node_osc_server, "dispatcher": dispatcher}
        
        self.target_frame_rate = self.settings.get("target_frame_rate", 30)
        self.use_push2_display = self.settings.get("use_push2_display", True)
        
        self.tasks = set()
        self.queue = []

    async def init_midi_calls(self, settings):
        await self.set_midi_in_channel(settings.get("midi_in_default_channel", 0))
        await self.set_midi_out_channel(settings.get("midi_out_default_channel", 0))
        await self.init_midi_in(device_name=settings.get("default_midi_in_device_name", None))
        await self.init_midi_out(
            device_name=settings.get("default_midi_out_device_name", None)
        )
        # TODO: this is a bodge and should be made to work without the try/except
        try:
            for port in iso.get_midi_input_names():
                if settings.get("default_midi_in_device_name") in port:
                    self.iso_midi_in_device_name = port
                    self.iso_midi_in = iso.MidiInputDevice(device_name=self.iso_midi_in_device_name)
                    self.global_timeline = iso.Timeline(output_device=iso.DummyOutputDevice(), clock_source=self.iso_midi_in)
                    # self.global_timeline.background()
            
            if self.iso_midi_in_device_name == None:
                self.global_timeline = iso.Timeline(self.tempo, output_device=iso.DummyOutputDevice())
    
        except:
            if self.iso_midi_in_device_name == None:
                self.global_timeline = iso.Timeline(self.tempo, output_device=iso.DummyOutputDevice())
                
        await self.init_notes_midi_in(
            device_name=settings.get("default_notes_midi_in_device_name", None)
        )
    async def init_modes(self, settings):
        self.instrument_selection_mode = InstrumentSelectionMode(
            self, settings=settings
        )

        self.main_controls_mode = MainControlsMode(self, settings=settings)
        self.active_modes.append(self.main_controls_mode)

        self.melodic_mode = MelodicMode(
            self, settings=settings, send_osc_func=self.send_osc
        )
        self.rhythmic_mode = RhythmicMode(self, settings=settings)
        self.slice_notes_mode = SliceNotesMode(self, settings=settings)
        await self.set_melodic_mode()

        self.preset_selection_mode = PresetSelectionMode(self, settings=settings)
        self.trig_edit_mode = TrigEditMode(self, settings=settings)
        
        # Must be initialized after instrument selection mode so it gets info about loaded instruments
        self.midi_cc_mode = MIDICCMode(
            self, settings=settings
        )  
        
        # Must be initialized after instrument selection mode so it gets info about loaded instruments
        self.osc_mode = OSCMode(
            self, settings=settings
        )
        
        self.sequencer_mode = SequencerMode(
            self, settings=settings, send_osc_func=self.send_osc
        )
        self.metro_sequencer_mode = MetroSequencerMode(
            self, settings=settings, send_osc_func=self.send_osc
        ) 
        self.active_modes += [self.instrument_selection_mode, self.osc_mode]
        self.instrument_selection_mode.select_instrument(
            self.instrument_selection_mode.selected_instrument
        )  
        self.ddrm_tone_selector_mode = DDRMToneSelectorMode(self, settings=settings)
        self.menu_mode = MenuMode(self, settings=settings, send_osc_func=self.send_osc)
        self.settings_mode = SettingsMode(self, settings=settings)
        self.mute_mode = MuteMode(self, settings=settings) 
        overwitch_def = {
            "instrument_name": "Overwitch",
            "instrument_short_name": "Overwitch",
            "midi_channel": 9
            }
        self.external_instruments = [ExternalInstrument(self, 'Overwitch', overwitch_def)]
        
    async def get_all_modes(self):
        return [
            getattr(self, element)
            for element in vars(self)
            if isinstance(getattr(self, element), definitions.PyshaMode)
        ]

    async def is_mode_active(self, mode):
        return mode in self.active_modes

    async def toggle_and_rotate_settings_mode(self):
        if self.is_mode_active(self.settings_mode):
            rotation_finished = await self.settings_mode.move_to_next_page()
            if rotation_finished:
                self.active_modes = [
                    mode for mode in self.active_modes if mode != self.settings_mode
                ]
                await self.settings_mode.deactivate()
        else:
            self.active_modes.append(self.settings_mode)
            await self.settings_mode.activate()

    async def toggle_menu_mode(self):
        # print("toggle menu mode")
        previous_mode = self.previously_active_mode_for_xor_group
        # print("modes:",previous_mode)
        # instrument = self.osc_mode.get_current_instrument()
        # instrument.query_slots()
        if await self.is_mode_active(self.menu_mode):
            # Deactivate (replace ddrm tone selector mode by midi cc and instrument selection mode)
            new_active_modes = []
            for mode in self.active_modes:
                if mode != self.menu_mode:
                    new_active_modes.append(mode)

            self.active_modes = new_active_modes
            # new_active_modes.append(previous_mode)
            
            await self.menu_mode.deactivate()
        else:
            # Activate (replace midi cc and instrument selection mode by ddrm tone selector mode)
            # print(self.active_modes)
            self.previously_active_mode_for_xor_group = self.active_modes[-1]
            
            new_active_modes = []
            for mode in self.active_modes:
                if mode != self.preset_selection_mode:
                    new_active_modes.append(mode)

            new_active_modes.append(self.menu_mode)
            self.active_modes = new_active_modes
            await self.preset_selection_mode.deactivate()
            await self.trig_edit_mode.deactivate()
            await self.menu_mode.activate()

    # TODO: preset sel/trig edit get wonky when switching from one to another
    # One triggering needs to shut down another

    async def toggle_preset_selection_mode(self):
        
        previous_mode = self.previously_active_mode_for_xor_group
        if await self.is_mode_active(self.preset_selection_mode):
            # Deactivate (replace ddrm tone selector mode by midi cc and instrument selection mode)
            new_active_modes = []
            for mode in self.active_modes:
                if mode != self.preset_selection_mode:
                    new_active_modes.append(mode)
            new_active_modes.append(self.osc_mode)
            # new_active_modes.append(previous_mode)
            self.active_modes = new_active_modes
            await self.preset_selection_mode.deactivate()
            await self.metro_sequencer_mode.activate()
            await self.osc_mode.activate()
        else:
            # Activate (replace midi cc and instrument selection mode by ddrm tone selector mode)
            # self.previously_active_mode_for_xor_group = self.active_modes[-1]
            new_active_modes = []
            for mode in self.active_modes:
                if mode != self.menu_mode and mode != self.osc_mode and mode != self.trig_edit_mode:
                    new_active_modes.append(mode)
            new_active_modes.append(self.preset_selection_mode)
            self.active_modes = new_active_modes
            await self.menu_mode.deactivate()
            await self.osc_mode.deactivate()
            await self.trig_edit_mode.deactivate()
            await self.metro_sequencer_mode.deactivate()
            await self.preset_selection_mode.activate()
            # print(self.active_modes, "active modes")


    async def toggle_trig_edit_mode(self):
        previous_mode = self.previously_active_mode_for_xor_group
        if await self.is_mode_active(self.trig_edit_mode):
            # Deactivate (replace ddrm tone selector mode by midi cc and instrument selection mode)
            new_active_modes = []
            for mode in self.active_modes:
                if mode != self.trig_edit_mode:
                    new_active_modes.append(mode)

            await new_active_modes.append(self.osc_mode)
            await new_active_modes.append(previous_mode)
            self.active_modes = new_active_modes
            await self.osc_mode.activate()
            await self.trig_edit_mode.deactivate()
        else:
            # Activate (replace midi cc and instrument selection mode by ddrm tone selector mode)
            self.previously_active_mode_for_xor_group = self.active_modes[-1]
            new_active_modes = []
            for mode in self.active_modes:
                if mode != self.menu_mode and mode != self.osc_mode and mode != self.preset_selection_mode:
                    new_active_modes.append(mode)

            new_active_modes.append(self.trig_edit_mode)
            self.active_modes = new_active_modes
            await self.menu_mode.deactivate()
            await self.osc_mode.deactivate()
            await self.trig_edit_mode.activate()
            await self.metro_sequencer_mode.deactivate()
            await self.preset_selection_mode.deactivate()
            # print(self.active_modes, "active modes")

    async def toggle_ddrm_tone_selector_mode(self):
        previous_mode = self.previously_active_mode_for_xor_group
        if await self.is_mode_active(self.ddrm_tone_selector_mode):
            # Deactivate (replace ddrm tone selector mode by midi cc and instrument selection mode)
            new_active_modes = []
            for mode in self.active_modes:
                if mode != self.ddrm_tone_selector_mode:
                    new_active_modes.append(mode)
                else:
                    new_active_modes.append(self.instrument_selection_mode)
                    new_active_modes.append(self.osc_mode)
            self.active_modes = new_active_modes
            new_active_modes.append(previous_mode)
            await self.ddrm_tone_selector_mode.deactivate()
            await self.osc_mode.activate()
            await self.instrument_selection_mode.activate()
        else:
            # Activate (replace midi cc and instrument selection mode by ddrm tone selector mode)
            self.previously_active_mode_for_xor_group = self.active_modes[-1]
            new_active_modes = []
            for mode in self.active_modes:
                if mode != self.instrument_selection_mode and mode != self.osc_mode:
                    new_active_modes.append(mode)
                elif mode == self.osc_mode:
                    new_active_modes.append(self.ddrm_tone_selector_mode)
            self.active_modes = new_active_modes
            await self.osc_mode.deactivate()
            await self.metro_sequencer_mode.deactivate()
            await self.instrument_selection_mode.deactivate()
            await self.ddrm_tone_selector_mode.activate()

    async def set_mode_for_xor_group(self, mode_to_set):
        """This activates the mode_to_set, but makes sure that if any other modes are currently activated
        for the same xor_group, these other modes get deactivated. This also stores a reference to the
        latest active mode for xor_group, so once a mode gets unset, the previously active one can be
        automatically set"""
        if not await self.is_mode_active(mode_to_set):
            # First deactivate all existing modes for that xor group
            new_active_modes = []
            for mode in self.active_modes:
                try:
                    if (
                        mode.xor_group is not None
                        and mode.xor_group == mode_to_set.xor_group
                    ):
                        await mode.deactivate()
                        self.previously_active_mode_for_xor_group[mode.xor_group] = (
                            mode  # Store last mode that was active for the group
                        )
                    else:
                        new_active_modes.append(mode)
                except:
                    pass
            self.active_modes = new_active_modes

            # Now add the mode to set to the active modes list and activate it
            new_active_modes.append(mode_to_set)
            await mode_to_set.activate()

    async def unset_mode_for_xor_group(self, mode_to_unset):
        """This deactivates the mode_to_unset and reactivates the previous mode that was active for this xor_group.
        This allows to make sure that one (and onyl one) mode will be always active for a given xor_group.
        """
        if await self.is_mode_active(mode_to_unset):

            # Deactivate the mode to unset
            self.active_modes = [
                mode for mode in self.active_modes if mode != mode_to_unset
            ]
            await mode_to_unset.deactivate()

            # Activate the previous mode that was activated for the same xor_group. If none listed, activate a default one
            previous_mode = self.previously_active_mode_for_xor_group.get(
                mode_to_unset.xor_group, None
            )
            if previous_mode is not None:
                del self.previously_active_mode_for_xor_group[mode_to_unset.xor_group]
                await self.set_mode_for_xor_group(previous_mode)
            else:
                # Enable default
                # TODO: here we hardcoded the default mode for a specific xor_group, I should clean this a little bit in the future...
                if mode_to_unset.xor_group == "pads":
                    await self.set_mode_for_xor_group(self.melodic_mode)

    async def toggle_melodic_rhythmic_slice_modes(self):
        if await self.is_mode_active(self.metro_sequencer_mode):
            await self.set_melodic_mode()
        elif await self.is_mode_active(self.melodic_mode):
            await self.set_metro_sequencer_mode()
        else:
            # If none of melodic or rhythmic or slice modes were active, enable melodic by default
            await self.set_metro_sequencer_mode()

    async def set_melodic_mode(self):
        await self.set_mode_for_xor_group(self.melodic_mode)

    async def set_rhythmic_mode(self):
        await self.set_mode_for_xor_group(self.rhythmic_mode)

    async def set_slice_notes_mode(self):
        await self.set_mode_for_xor_group(self.slice_notes_mode)

    async def set_sequencer_mode(self):
        # pass
        await self.set_mode_for_xor_group(self.sequencer_mode)

    async def set_metro_sequencer_mode(self):
        # pass
        await self.set_mode_for_xor_group(self.metro_sequencer_mode)

    async def set_mute_mode(self):
        if await self.is_mode_active(self.preset_selection_mode):
            await self.toggle_preset_selection_mode()
        try:
            await self.set_mode_for_xor_group(self.mute_mode)
        except Exception as e:
            print(e)

    async def set_preset_selection_mode(self):
        self.set_mode_for_xor_group(self.preset_selection_mode)

    async def unset_preset_selection_mode(self):
        self.unset_mode_for_xor_group(self.preset_selection_mode)

    async def save_current_settings_to_file(self):
        # NOTE: when saving device names, eliminate the last bit with XX:Y numbers as this might vary across runs
        # if different devices are connected
        settings = {
            "midi_in_default_channel": self.midi_in_channel,
            "midi_out_default_channel": self.midi_out_channel,
            "default_midi_in_device_name": (
                self.midi_in.name[:-4] if self.midi_in is not None else None
            ),
            "default_midi_out_device_name": (
                self.midi_out.name[:-4] if self.midi_out is not None else None
            ),
            "default_notes_midi_in_device_name": (
                self.notes_midi_in.name[:-4] if self.notes_midi_in is not None else None
            ),
            "use_push2_display": self.use_push2_display,
            "target_frame_rate": self.target_frame_rate,
        }
        for mode in await self.get_all_modes():
            mode_settings = await mode.get_settings_to_save()
            if mode_settings:
                await settings.update(mode_settings)
        json.dump(settings, open("settings.json", "w"))

    async def init_midi_in(self, device_name=None):
        print("Configuring MIDI in to {}...".format(device_name))
        self.available_midi_in_device_names = [
            name
            for name in mido.get_input_names()
            if "Ableton Push" not in name
            and "RtMidi" not in name
            and "Through" not in name
        ]
        if device_name is not None:
            try:
                full_name = [
                    name
                    for name in self.available_midi_in_device_names
                    if device_name in name
                ][0]
            except IndexError:
                full_name = None
            if full_name is not None:
                if self.midi_in is not None:
                    self.midi_in.callback = None  # Disable current callback (if any)
                try:
                    self.midi_in = mido.open_input(full_name)
                    self.midi_in.callback = self.midi_in_handler
                    print('Receiving MIDI in from "{0}"'.format(full_name))
                except IOError:
                    print(
                        'Could not connect to MIDI input port "{0}"\nAvailable device names:'.format(
                            full_name
                        )
                    )
                    for name in self.available_midi_in_device_names:
                        print(" - {0}".format(name))
            else:
                print("No available device name found for {}".format(device_name))
        else:
            if self.midi_in is not None:
                self.midi_in.callback = None  # Disable current callback (if any)
                self.midi_in.close()
                self.midi_in = None

        if self.midi_in is None:
            print("Not receiving from any MIDI input")

    async def init_midi_out(self, device_name=None):
        pass
        # print("Configuring MIDI out to {}...".format(device_name))
        # self.available_midi_out_device_names = [
        #     name
        #     for name in mido.get_output_names()
        #     if "Ableton Push" not in name
        #     and "RtMidi" not in name
        #     and "Through" not in name
        # ]
        # self.available_midi_out_device_names += [
        #     "Pushpin 0",
        #     "Pushpin 1",
        #     "Pushpin 2",
        #     "Pushpin 3",
        #     "Pushpin 4",
        #     "Pushpin 5",
        #     "Pushpin 6",
        #     "Pushpin 7",
        # ]
        # virtual_device_names = [
        #     "Pushpin 0",
        #     "Pushpin 1",
        #     "Pushpin 2",
        #     "Pushpin 3",
        #     "Pushpin 4",
        #     "Pushpin 5",
        #     "Pushpin 6",
        #     "Pushpin 7",
        # ]
        # if device_name is not None:
        #     try:
        #         full_name = [
        #             name
        #             for name in self.available_midi_out_device_names
        #             if device_name in name
        #         ][0]
        #     except IndexError:
        #         full_name = None
        #     if full_name is not None:
        #         try:
        #             if full_name in virtual_device_names:
        #                 self.midi_out = mido.open_output(full_name, virtual=True)
        #             else:
        #                 self.midi_out = mido.open_output(full_name)
        #             print('Will send MIDI to "{0}"'.format(full_name))
        #         except IOError:
        #             print(
        #                 'Could not connect to MIDI output port "{0}"\nAvailable device names:'.format(
        #                     full_name
        #                 )
        #             )
        #             for name in self.available_midi_out_device_names:
        #                 print(" - {0}".format(name))
        #     else:
        #         print("No available device name found for {}".format(device_name))
        # else:
        #     if self.midi_out is not None:
        #         self.midi_out.close()
        #         self.midi_out = None

        # if self.midi_out is None:
        #     print("Won't send MIDI to any device")

    async def init_notes_midi_in(self, device_name=None):
        print("Configuring notes MIDI in to {}...".format(device_name))
        self.available_midi_in_device_names = [
            name
            for name in mido.get_input_names()
            if "Ableton Push" not in name
            and "RtMidi" not in name
            and "Through" not in name
        ]

        if device_name is not None:
            try:
                full_name = [
                    name
                    for name in self.available_midi_in_device_names
                    if device_name in name
                ][0]
            except IndexError:
                full_name = None
            if full_name is not None:
                if self.notes_midi_in is not None:
                    self.notes_midi_in.callback = (
                        None  # Disable current callback (if any)
                    )
                try:
                    self.notes_midi_in = mido.open_input(full_name)
                    self.notes_midi_in.callback = self.notes_midi_in_handler
                    print('Receiving notes MIDI in from "{0}"'.format(full_name))
                except IOError:
                    print(
                        'Could not connect to notes MIDI input port "{0}"\nAvailable device names:'.format(
                            full_name
                        )
                    )
                    for name in self.available_midi_in_device_names:
                        print(" - {0}".format(name))
            else:
                print("No available device name found for {}".format(device_name))
        else:
            if self.notes_midi_in is not None:
                self.notes_midi_in.callback = None  # Disable current callback (if any)
                self.notes_midi_in.close()
                self.notes_midi_in = None

        if self.notes_midi_in is None:
            print("Could not configures notes MIDI input")

    async def set_midi_in_channel(self, channel, wrap=False):
        self.midi_in_channel = channel
        if self.midi_in_channel < -1:  # Use "-1" for "all channels"
            self.midi_in_channel = -1 if not wrap else 15
        elif self.midi_in_channel > 15:
            self.midi_in_channel = 15 if not wrap else -1

    async def set_midi_out_channel(self, channel, wrap=False):
        # We use channel -1 for the "instrument setting" in which midi channel is taken from currently selected instrument
        self.midi_out_channel = channel
        if self.midi_out_channel < -1:
            self.midi_out_channel = -1 if not wrap else 15
        elif self.midi_out_channel > 15:
            self.midi_out_channel = 15 if not wrap else -1

    async def set_osc_in_port(self, port, wrap=False):
        # We use channel -1 for the "instrument setting" in which midi channel is taken from currently selected instrument
        self.osc_in_port = port
        if self.osc_in_port < 1030:
            self.osc_in_port = -1 if not wrap else 10
        elif self.osc_in_port > 1038:
            self.osc_in_port = 15 if not wrap else -1

    async def set_midi_in_device_by_index(self, device_idx):
        if device_idx >= 0 and device_idx < len(self.available_midi_in_device_names):
            await self.init_midi_in(self.available_midi_in_device_names[device_idx])
        else:
            await self.init_midi_in(None)

    async def set_midi_out_device_by_index(self, device_idx):
        if device_idx >= 0 and device_idx < len(self.available_midi_out_device_names):
            await self.init_midi_out(self.available_midi_out_device_names[device_idx])
        else:
            await self.init_midi_out(None)

    async def set_notes_midi_in_device_by_index(self, device_idx):
        if device_idx >= 0 and device_idx < len(self.available_midi_in_device_names):
            await self.init_notes_midi_in(self.available_midi_in_device_names[device_idx])
        else:
            await self.init_notes_midi_in(None)

    async def send_midi(self, msg, use_original_msg_channel=False):
        # Unless we specifically say we want to use the original msg mnidi channel, set it to global midi out channel or to the channel of the current instrument
        if not use_original_msg_channel and hasattr(msg, "channel"):
            midi_out_channel = self.midi_out_channel
            if self.midi_out_channel == -1:
                # Send the message to the midi channel of the currently selected instrument (or to instrument 1 if selected instrument has no midi channel information)
                instrument_midi_channel = (
                    await self.instrument_selection_mode.get_current_instrument_info()[
                        "midi_channel"
                    ]
                )
                if instrument_midi_channel == -1:
                    midi_out_channel = 0
                else:
                    midi_out_channel = (
                        instrument_midi_channel - 1
                    )  # msg.channel is 0-indexed
            msg = msg.copy(channel=midi_out_channel)

        if self.midi_out is not None:
            self.midi_out.send(msg)

    async def send_osc(self, address, value, instrument_short_name=None):
        # print(
        #     instrument_short_name,
        #     self.instrument_selection_mode.get_current_instrument_short_name(),
        #     "SEND OSC",
        # )
        # print("App.py send_osc", address, value, instrument_short_name)
        try:
            if instrument_short_name is not None:
                # This is for the sequencer
                client = self.instruments[instrument_short_name].osc.get(
                    "client", None
                )
                if client:
                    client.send_message(address, value)
            else:
                # This is for wiggling knobs
                client = self.instruments[
                    await self.instrument_selection_mode.get_current_instrument_short_name()
                ].get("client", None)

                if client:
                    await client.send_message(address, value)
                # print("adress", address, value)
        except Exception as e:
            print("Exception in app.py send_osc")
            traceback.print_exc()

    async def send_osc_multi(self, commands, instrument_short_name=None):
        for command in commands:
            address, val = command
            await self.send_osc(address, val, instrument_short_name)

    async def midi_in_handler(self, msg):
        # if msg.type != 'clock':
        #     print(msg.type)
        
        # TODO: Does this work without midi in? I think it should
        # TODO: I think we need to reset the seq playhead_track on start or maybe stop
        # so that the clocks line up proper
        if msg.type == "stop":
            self.metro_sequencer_mode.sequencer_is_playing = False
            for (instrument_short_name) in await self.metro_sequencer_mode.get_all_distinct_instrument_short_names_helper():
                sequencer = self.metro_sequencer_mode.instrument_sequencers[instrument_short_name]
                # sequencer.reschedule_playhead_track()
        
        if msg.type == "start" or msg.type == "continue":
            self.metro_sequencer_mode.sequencer_is_playing = True
            # self.metro_sequencer_mode.reschedule_playhead_tracks()
        
        if msg.type == "songpos" or msg.type == "stop":
            # self.metro_sequencer_mode.sequencer_is_playing = False
            for (instrument_short_name) in await self.metro_sequencer_mode.get_all_distinct_instrument_short_names_helper():
                
                try:
                    sequencer = self.metro_sequencer_mode.instrument_sequencers[instrument_short_name]
                    await sequencer.reset_index()
                    sequencer.scale_count = 0
                    sequencer.next_step_index = 0
                except Exception as e:
                    print(e)
                try:
                    await self.global_timeline.reset()
                except Exception as e:
                    print(e)
            # shouldn't this be just update_pads
            await self.metro_sequencer_mode.update_pads_to_seq_state()
                
        if hasattr(msg, "channel"):
            instrument = next(
                (
                    item
                    for item in self.instrument_selection_mode.instruments_info
                    if item["midi_channel"] == msg.channel
                ),
                None,
            )
            if instrument:
                instance = self.instruments.get(instrument["instrument_short_name"], None)
                if instance.midi_in_device:
                    instance.midi_in_device.send(msg)
            # This will rule out sysex and other "strange" messages that don't have channel info
            # if (
            #     self.midi_in_channel == -1 or msg.channel == self.midi_in_channel
            # ):  # If midi input channel is set to -1 (all) or a specific channel

            #     skip_message = False
            #     if msg.type == "aftertouch":
            #         now = time.time()
            #         if (abs(self.last_cp_value_recevied - msg.value) > 10) and (
            #             now - self.last_cp_value_recevied_time < 0.5
            #         ):
            #             skip_message = True
            #         else:
            #             self.last_cp_value_recevied = msg.value
            #         self.last_cp_value_recevied_time = time.time()

            #     if not skip_message:
            #         # Forward message to the main MIDI out
            #         self.send_midi(msg)

            #         # Forward the midi message to the active modes
            #         for mode in self.active_modes:
            #             mode.on_midi_in(msg, source=self.midi_in.name)

    async def notes_midi_in_handler(self, msg):
        # Check if message is note on or off and check if the MIDI channel is the one assigned to the currently selected instrument
        # Then, send message to the melodic/rhythmic active modes so the notes are shown in pads/keys
        if msg.type == "note_on" or msg.type == "note_off":
            instrument_midi_channel = (
                await self.instrument_selection_mode.get_current_instrumentument_info()[
                    "midi_channel"
                ]
            )
            if msg.channel == instrument_midi_channel - 1:  # msg.channel is 0-indexed
                for mode in self.active_modes:
                    if mode == self.melodic_mode or mode == self.rhythmic_mode:
                        mode.on_midi_in(msg, source=self.notes_midi_in.name)


    async def add_display_notification(self, text):
        self.notification_text = text
        self.notification_time = time.time()

    async def init_jack_server(self):

        argv = iter(sys.argv)
        # By default, use script name without extension as client name:
        defaultclientname = os.path.splitext(os.path.basename(next(argv)))[0]
        clientname = next(argv, defaultclientname)
        servername = next(argv, None)

        client = jack.Client(clientname, servername=servername)
        client.blocksize = 512
        if client.status.server_started:
            print("JACK server started")
        if client.status.name_not_unique:
            print(f"unique name {client.name!r} assigned")

        @client.set_process_callback
        def process(frames):
            assert len(client.inports) == len(client.outports)
            assert frames == client.blocksize
            for i, o in zip(client.inports, client.outports):
                o.get_buffer()[:] = i.get_buffer()

        @client.set_shutdown_callback
        def shutdown(status, reason):
            print("JACK shutdown!")
            print("status:", status)
            print("reason:", reason)
            # event.set()

        client.activate()
        # # create two port pairs
        # for number in 1, 2:
        #     client.inports.register(f"input_{number}")
        #     client.outports.register(f"output_{number}")

        # with client:
        #     # When entering this with-statement, client.activate() is called.
        #     # This tells the JACK server that we are ready to roll.
        #     # Our process() callback will start running now.

        #     # Connect the ports.  You can't do this before the client is activated,
        #     # because we can't make connections to clients that aren't running.
        #     # Note the confusing (but necessary) orientation of the driver backend
        #     # ports: playback ports are "input" to the backend, and capture ports
        #     # are "output" from it.

        #     capture = client.get_ports(is_physical=True, is_output=True)
        #     if not capture:
        #         raise RuntimeError("No physical capture ports")

        #     for src, dest in zip(capture, client.inports):
        #         client.connect(src, dest)

        #     playback = client.get_ports(is_physical=True, is_input=True)
        #     if not playback:
        #         raise RuntimeError("No physical playback ports")

        #     for src, dest in zip(client.outports, playback):
        #         client.connect(src, dest)

        #     print("Press Ctrl+C to stop")
        #     try:
        #         event.wait()
        #     except KeyboardInterrupt:
        #         print("\nInterrupted by user")

        # When the above with-statement is left (either because the end of the
        # code block is reached, or because an exception was raised inside),
        # client.deactivate() and client.close() are called automatically.

    async def init_push(self):
        print("Configuring Push...")
        self.push = push2_python.Push2()
        if platform.system() == "Linux":
            # When this app runs in Linux is because it is running on the Raspberrypi
            #  I've overved problems trying to reconnect many times withotu success on the Raspberrypi, resulting in
            # "ALSA lib seq_hw.c:466:(snd_seq_hw_open) open /dev/snd/seq failed: Cannot allocate memory" issues.
            # A work around is make the reconnection time bigger, but a better solution should probably be found.
            self.push.set_push2_reconnect_call_interval(2)
            
        # for y in range(0, 8):
        #     for x in range(0, 8):
        #         self.push.pads.set_pad_color((x, y), color=definitions.OFF_BTN_COLOR)

    async def update_push2_pads(self):
        for mode in self.active_modes:
            await mode.update_pads()

    async def update_push2_buttons(self):
        for mode in self.active_modes:
            await mode.update_buttons()

    async def update_push2_display(self):
        if self.use_push2_display:
            # Prepare cairo canvas
            w, h = (
                push2_python.constants.DISPLAY_LINE_PIXELS,
                push2_python.constants.DISPLAY_N_LINES,
            )
            surface = cairo.ImageSurface(cairo.FORMAT_RGB16_565, w, h)
            ctx = cairo.Context(surface)

            # Call all active modes to write to context
            for mode in self.active_modes:
                    await mode.update_display(ctx, w, h)
            # Makes seq submenus always draw on top of other modes
            await self.sequencer_mode.update_display(ctx, w, h)
            await self.metro_sequencer_mode.update_display(ctx, w, h)

            # Show any notifications that should be shown
            if self.notification_text is not None:
                time_since_notification_started = time.time() - self.notification_time
                if time_since_notification_started < definitions.NOTIFICATION_TIME:
                    show_notification(
                        ctx,
                        self.notification_text,
                        opacity=1
                        - time_since_notification_started
                        / definitions.NOTIFICATION_TIME,
                    )
                else:
                    self.notification_text = None

            # Convert cairo data to numpy array and send to push
            buf = surface.get_data()
            frame = numpy.ndarray(
                shape=(h, w), dtype=numpy.uint16, buffer=buf
            ).transpose()
            self.push.display.display_frame(
                frame, input_format=push2_python.constants.FRAME_FORMAT_RGB565
            )

    async def check_for_delayed_actions(self):
        # If MIDI not configured, make sure we try sending messages so it gets configured
        if not self.push.midi_is_configured():
            self.push.configure_midi()

        # Call dalyed actions in active modes
        for mode in self.active_modes:
            await mode.check_for_delayed_actions()

        if self.pads_need_update:
            await self.update_push2_pads()
            self.pads_need_update = False

        if self.buttons_need_update:
            await self.update_push2_buttons()
            self.buttons_need_update = False
    
    async def queue_tasks(self):
        for task in self.queue:
            if task:
                t = asyncio.create_task(task)
                self.tasks.add(t)
                t.add_done_callback(self.tasks.discard)
            
            self.queue.remove(task)


    async def run_loop(self):
        print("Loading State ...")
        # self.sequencer_mode.load_state()
        await self.metro_sequencer_mode.load_state()
        await self.preset_selection_mode.init_surge_preset_state()
        
        for idx, instrument_shortname in enumerate(self.instruments):
            instrument = self.instruments[instrument_shortname]
                
            await self.preset_selection_mode.load_init_state(instrument_shortname=instrument_shortname)
            # instrument.update_current_devices()


        # self.osc_mode.load_state()
        
        print("Pysha is running...")
        while True:
            before_draw_time = time.time()

            # Draw ui
            await self.update_push2_display()

            # Frame rate measurement
            now = time.time()
            self.current_frame_rate_measurement += 1
            if time.time() - self.current_frame_rate_measurement_second > 1.0:
                self.actual_frame_rate = self.current_frame_rate_measurement
                self.current_frame_rate_measurement = 0
                self.current_frame_rate_measurement_second = now
                # Uncomment to display FPS in terminal
                # print('{0} fps'.format(self.actual_frame_rate))

            # Check if any delayed actions need to be applied
            await self.check_for_delayed_actions()

            # Schedule tasks from queue
            await self.queue_tasks()

            after_draw_time = time.time()

            # Calculate sleep time to aproximate the target frame rate
            sleep_time = (1.0 / self.target_frame_rate) - (
                after_draw_time - before_draw_time
            )

            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(0)

    async def on_midi_push_connection_established(self):
        # Do initial configuration of Push
        print("Doing initial Push config...")

        # Force configure MIDI out (in case it wasn't...)
        app.push.configure_midi_out()

        # Configure custom color palette
        app.push.color_palette = {}
        for count, color_name in enumerate(definitions.COLORS_NAMES):
            app.push.set_color_palette_entry(
                count,
                [color_name, color_name],
                rgb=definitions.get_color_rgb_float(color_name),
                allow_overwrite=True,
            )
        app.push.reapply_color_palette()

        # Initialize all buttons to black, initialize all pads to off
        app.push.buttons.set_all_buttons_color(color=definitions.BLACK)
        app.push.pads.set_all_pads_to_color(color=definitions.BLACK)

        # Iterate over modes and (re-)activate them
        for mode in self.active_modes:
            mode.activate()

        # Update buttons and pads (just in case something was missing!)
        await app.update_push2_buttons()
        await app.update_push2_pads()

    async def get_pipewire_config(self):
        try:
            proc = await asyncio.create_subprocess_shell(
                f"pw-dump -N",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if stdout:
                self.pipewire = json.loads(stdout.decode().strip())
            if stderr:
                print(stderr)
        except Exception as e:
            traceback.print_exc()
            print("Waiting 2 seconds for device to become available and trying again...")
            await asyncio.sleep(2)
            await self.get_pipewire_config()



    
    async def start_pd_node(self, file_index = 8):
        self.pd_process = await asyncio.create_subprocess_exec(
            "pw-jack",
            "-p",
            "128",
            "puredata",
            "-jack",
            "-nogui",
            "-rt",
            "-channels",
            "16",
            "-nocallback",
            f"./puredata_nodes/passthrough_{file_index}.pd",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.PIPE,
            
        )
        
        self.puredata_process_id = self.pd_process.pid
        
    async def get_volume_client(self):
        for item in self.pipewire:
            if item["type"] == "PipeWire:Interface:Client":
                # print(item.get("info", {}).get("props", {}).get("application.process.id",None), self.puredata_process_id)
                try:
                    id = item.get("info", {}).get("props", {}).get("application.process.id",None)
                    if id == self.puredata_process_id:
                        self.volume_client = item
                        self.puredata_client_id = self.volume_client.get("id", None)
                except:
                    pass
        
        return self.volume_client


    async def get_volume_node(self):
        for node in self.pipewire:
            if node["type"] == "PipeWire:Interface:Node":
                try:
                    id = node.get("info", {}).get("props", {}).get("client.id",None)
                    if id == self.puredata_client_id:
                        self.volume_node = node
                except:
                    pass
        return self.volume_node
        
        
    async def disconnect_links_from_volume_node(self):
        # init_links = [link for link in self.pipewire if link['type'] == 'PipeWire:Interface:Link' and link['info']['output-node-id'] == self.volume_node['id']]
        link_list = []
        for link in self.pipewire: 
            if link['type'] == 'PipeWire:Interface:Link':
                # print(link['info']['output-node-id'], "  ", link['info']['input-node-id'], "  ", self.volume_node['id'], )
                if link['info']['output-node-id'] == self.volume_node['id'] or link['info']['input-node-id'] == self.volume_node['id']:
                    link_list.append(link)
        for link in link_list:
            await disconnectPipewireLink(link['id'])
    
        # print("disconnected __________")
    
    async def set_main_volumes(self, *args):
        # TODO: need to make a client for all them nodes
        # This is done in instrument, just copy
        for idx, instrument in enumerate(self.instruments):
            left_channel_idx = idx * 2
            right_channel_idx = left_channel_idx + 1
            # Value only from left because we want to have it center
            volume_value = self.volumes[left_channel_idx]
            await self.volume_node_osc_client.send_message(f"/vol_{left_channel_idx}", float(volume_value))
            await self.volume_node_osc_client.send_message(f"/vol_{right_channel_idx}", float(volume_value))
        
  

# Bind push action handlers with class methods
@push2_python.on_encoder_rotated()
def on_encoder_rotated(_, encoder_name, increment):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_encoder_rotated(encoder_name, increment)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print("Error:  {}".format(str(e)))
        traceback.print_exc()


@push2_python.on_encoder_touched()
def on_encoder_touched(_, encoder_name):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_encoder_touched(encoder_name)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print("Error:  {}".format(str(e)))
        traceback.print_exc()


@push2_python.on_encoder_released()
def on_encoder_released(_, encoder_name):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_encoder_released(encoder_name)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print("Error:  {}".format(str(e)))
        traceback.print_exc()


@push2_python.on_pad_pressed()
def on_pad_pressed(_, pad_n, pad_ij, velocity):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_pad_pressed(pad_n, pad_ij, velocity)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print("Error:  {}".format(str(e)))
        traceback.print_exc()


@push2_python.on_pad_released()
def on_pad_released(_, pad_n, pad_ij, velocity):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_pad_released(pad_n, pad_ij, velocity)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print("Error:  {}".format(str(e)))
        traceback.print_exc()


@push2_python.on_pad_aftertouch()
def on_pad_aftertouch(_, pad_n, pad_ij, velocity):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_pad_aftertouch(pad_n, pad_ij, velocity)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print("Error:  {}".format(str(e)))
        traceback.print_exc()


@push2_python.on_button_pressed()
def on_button_pressed(_, name):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_button_pressed(name)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print("Error:  {}".format(str(e)))
        traceback.print_exc()


@push2_python.on_button_released()
def on_button_released(_, name):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_button_released(name)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print("Error:  {}".format(str(e)))
        traceback.print_exc()


@push2_python.on_touchstrip()
def on_touchstrip(_, value):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_touchstrip(value)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print("Error:  {}".format(str(e)))
        traceback.print_exc()


@push2_python.on_sustain_pedal()
def on_sustain_pedal(_, sustain_on):
    try:
        for mode in app.active_modes[::-1]:
            action_performed = mode.on_sustain_pedal(sustain_on)
            if action_performed:
                break  # If mode took action, stop event propagation
    except NameError as e:
        print("Error:  {}".format(str(e)))
        traceback.print_exc()


midi_connected_received_before_app = False


@push2_python.on_midi_connected()
def on_midi_connected(_):
    try:
        # TODO: this append might need to be removed?
        app.queue.append(app.on_midi_push_connection_established())
    except NameError as e:
        global midi_connected_received_before_app
        midi_connected_received_before_app = True
        # print("Error:  {}".format(str(e)))
        # traceback.print_exc()

async def main():
    # ow = await asyncio.create_subprocess_exec("overwitch-cli","-l", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    # stdout, stderr = await ow.communicate()
    # overwitch_devices = []
    
    # for dev in stdout.splitlines():
    #     """
    #     String Template:
    #     0: Analog Heat (ID 1935:000a) at bus 001, address 002
    #     """
    #     # TODO: this splitline will be key to state recall of overwitch connections
    #     m = re.search(r'(?P<device_number>\d+):\s(?P<device_name>[^\(]+)\(ID (?P<device_id>\d+:[^\)]+)\) at bus (?P<device_bus>\d+), address (?P<device_address>\d+)', dev)
        
    #     overwitch_devices.append({'idx': m.group('device_number'), 'name': m.group('device_name')})
    #     print(overwitch_devices)
    # Initialise OSC sockets
    loop = asyncio.get_event_loop()
    await app.init_midi_calls(app.settings)
    await app.init_push()
    await app.init_modes(app.settings)
    
    if midi_connected_received_before_app:
        # App received the "on_midi_connected" call before it was initialized. Do it now!
        print("Missed MIDI initialization call, doing it now...")
        await app.on_midi_push_connection_established()
    await app.start_pd_node()
    for index, instrument in enumerate(app.instruments):
        await app.instruments[instrument].start(loop)
        # await app.instruments[instrument].engine.start_pd_node()

    # for instrument in app.external_instruments:
    #     await instrument.start(loop)
        
    print("Initialising Pipewire support...")
    await asyncio.sleep(5)
    await app.get_pipewire_config()
    
    await app.get_volume_client()
    await app.get_volume_node()
    await app.disconnect_links_from_volume_node()
    await app.set_main_volumes()
    
    #Querry controls to update initial state

    for index, instrument in enumerate(app.instruments):
        # IDK why the fuck but after switch to JACK
        # The config_pw call makes surge-xt instances crash
        await app.instruments[instrument].engine.configure_pipewire()
        
        await app.instruments[instrument].init_devices_sync()
        app.global_timeline.add_output_device(app.instruments[instrument].midi_out_device)    
    for instrument in app.external_instruments:
        await instrument.engine.configure_pipewire()
    while True:
        await app.run_loop()


# Run app main loop
if __name__ == "__main__":
    try:
        app = PyshaApp()
        # if midi_connected_received_before_app:
        #     # App received the "on_midi_connected" call before it was initialized. Do it now!
        #     print("Missed MIDI initialization call, doing it now...")
        #     await app.on_midi_push_connection_established()

        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting Pysha...")
        try:
            app.push.f_stop.set()
            app.osc_mode.close_transports()
        except:
            pass
        # # cancel all tasks in the event loop
        # tasks = asyncio.all_tasks()
        # for task in tasks:
        #     task.cancel()