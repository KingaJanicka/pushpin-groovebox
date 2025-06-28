import definitions
from controllers import push2_constants
import push2_python
from sequencer.sequencer_metro import SequencerMetro
from modes.melodic_mode import MelodicMode
import isobar as iso
import os
import sys
import time
import json
import traceback
from user_interface.display_utils import show_text
from osc_controls import (
    OSCControl,
    ControlSpacer,
    OSCControlSwitch,
    OSCGroup,
)
from definitions import TRACK_NAMES_METRO

EMPTY_PATTERN = []

TRACK_COLORS = {
    TRACK_NAMES_METRO[0]: definitions.GREEN,
    TRACK_NAMES_METRO[1]: definitions.ORANGE,
    TRACK_NAMES_METRO[2]: definitions.YELLOW,
    TRACK_NAMES_METRO[3]: definitions.TURQUOISE,
    TRACK_NAMES_METRO[4]: definitions.RED,
    TRACK_NAMES_METRO[5]: definitions.CYAN,
    TRACK_NAMES_METRO[6]: definitions.CYAN,
    TRACK_NAMES_METRO[7]: definitions.CYAN,
}

track_button_names = [
    push2_python.constants.BUTTON_1_32T,
    push2_python.constants.BUTTON_1_32,
    push2_python.constants.BUTTON_1_16T,
    push2_python.constants.BUTTON_1_16,
    push2_python.constants.BUTTON_1_8T,
    push2_python.constants.BUTTON_1_8,
    # push2_python.constants.BUTTON_1_4T,
    # push2_python.constants.BUTTON_1_4,
]


class MetroSequencerMode(MelodicMode):
    sequencer_pad_matrix = [
        range(92, 100),
        range(84, 92),
        range(76, 84),
        range(68, 76),
        range(60, 68),
        range(52, 60),
        range(44, 52),
        range(36, 44),
    ]
    button_1_8_pressed = False
    button_1_4t_pressed = False
    button_1_4_pressed = False
    playhead = 0
    seq_tick = 0
    timeline_is_playing = False
    current_selected_section_and_page = {}
    instrument_sequencers = {}
    tempo = 120
    show_scale_menu = False
    global_timeline = None
    selected_track = TRACK_NAMES_METRO[0]
    scale_menu_filename = "scale_menu_metro.json"
    pads_press_time = [False] * 64
    pad_quick_press_time = 0.400
    disable_controls = False
    instrument_scale_edit_controls = {}
    scale_edit_controls = []
    metro_seq_pad_state = {}
    steps_held = []
    encoders_held = [False, False, False, False, False, False, False, False]
    encoder_incr_since_held = [False, False, False, False, False, False, False, False]
    encoder_short_press_time = 400000000
    rachets = {}
    major_scale = [0,2,4,5,7,9,11,12]
    def initialize(self, settings):
        super().initialize(settings)
        self.global_timeline = self.app.global_timeline
        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            self.instrument_sequencers[instrument_short_name] = SequencerMetro(
                self.app.instruments[instrument_short_name],
                self.sequencer_on_tick,
                self.playhead,
                self.send_osc_func,
                self.global_timeline,
                self.app,
            )
            self.rachets[instrument_short_name] = [
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
            ]
            self.instrument_scale_edit_controls[instrument_short_name] = {}
            self.metro_seq_pad_state[instrument_short_name] = {}
            for track_name in TRACK_NAMES_METRO:
                menu = []
                param_1 = OSCControl(
                    {
                        "$type": "control-range",
                        "label": "Gate Len",
                        "address": f"/",
                        "min": 0,
                        "max": 1,
                    },
                    self.get_current_instrument_color_helper,
                    None,
                )
                menu.append(param_1)
                
                
                param_2 = OSCControl(
                    {
                        "$type": "control-range",
                        "label": "Param 2",
                        "address": f"/",
                        "min": 2,
                        "max": 64,
                    },
                    self.get_current_instrument_color_helper,
                    None,
                )
                menu.append(param_2)


                param_3 = OSCControl(
                    {
                        "$type": "control-range",
                        "label": "Param 3",
                        "address": f"/",
                        "min": 2,
                        "max": 64,
                    },
                    self.get_current_instrument_color_helper,
                    None,
                )
                menu.append(param_3)

                param_4 = OSCControl(
                    {
                        "$type": "control-range",
                        "label": "Param 4",
                        "address": f"/",
                        "min": 2,
                        "max": 64,
                    },
                    self.get_current_instrument_color_helper,
                    None,
                )
                menu.append(param_4)

                param_5 = OSCControl(
                    {
                        "$type": "control-range",
                        "label": "Param 5",
                        "address": f"/",
                        "min": 2,
                        "max": 64,
                    },
                    self.get_current_instrument_color_helper,
                    None,
                )
                menu.append(param_5)
                param_6 = OSCControl(
                    {
                        "$type": "control-range",
                        "label": "Param 6",
                        "address": f"/",
                        "min": 2,
                        "max": 64,
                    },
                    self.get_current_instrument_color_helper,
                    None,
                )
                menu.append(param_6)
                seq_scale = OSCControl(
                    {
                        "$type": "control-range",
                        "label": "Seq Time Scale",
                        "address": f"/",
                        "min": 1,
                        "max": 32,
                    },
                    self.get_current_instrument_color_helper,
                    None,
                )
                seq_scale.value = 2
                menu.append(seq_scale)
                len = OSCControl(
                    {
                        "$type": "control-range",
                        "label": "Seq Steps",
                        "address": f"/",
                        "min": 2,
                        "max": 64,
                    },
                    self.get_current_instrument_color_helper,
                    None,
                )
                len.value = 64
                menu.append(len)
                self.instrument_scale_edit_controls[instrument_short_name] = menu
                self.metro_seq_pad_state[instrument_short_name][track_name] = [
                    [False, False, False, False, False, False, False, False],
                    [False, False, False, False, False, False, False, False],
                    [False, False, False, False, False, False, False, False],
                    [False, False, False, False, False, False, False, False],
                    [False, False, False, False, False, False, False, False],
                    [False, False, False, False, False, False, False, False],
                    [False, False, False, False, False, False, False, False],
                    [True, True, True, True, True, True, True, True],
                ]

    def update_pads_to_seq_state(self):
        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            seq = self.instrument_sequencers[instrument_short_name]
            
            # this updates all the pitch tracks
            pitch_track_name = TRACK_NAMES_METRO[0]
            pitch_seq_track = seq.get_track_by_name(pitch_track_name)
            pitch_pad_state = self.metro_seq_pad_state[instrument_short_name][pitch_track_name]
            
            for idx in range(8):
                pitch_val = pitch_seq_track[idx * 8]
                
                # for single pads
                if pitch_val in self.major_scale:
                    pitch_val_idx = self.major_scale.index(pitch_val)
                    for y in range(8):
                        if pitch_val_idx == y: 
                            pitch_pad_state[7 - y][idx] = True
                        else:
                            pitch_pad_state[7 - y][idx] = False
                
                # for double pads
                else:
                    # Turn off all pads, turn on the two we need
                    pitch_val_idx = self.major_scale.index(pitch_val - 1)
                    for y in range(8):
                        pitch_pad_state[7-y][idx] = False
                    pitch_pad_state[7 - pitch_val_idx][idx] = True
                    pitch_pad_state[6 - pitch_val_idx][idx] = True
                            
                        
            
            # this updates all the octave tracks
            octave_track_name = TRACK_NAMES_METRO[1]
            octave_seq_track = seq.get_track_by_name(octave_track_name)
            octave_pad_state = self.metro_seq_pad_state[instrument_short_name][octave_track_name]
            
            for idx in range(8):
                octave_val = octave_seq_track[idx * 8]
                for y in range(8):
                    if octave_val == y: 
                        octave_pad_state[7 - y][idx] = True
                    else:
                        octave_pad_state[7 - y][idx] = False
                        
            # this updates all the velocity tracks
            velocity_track_name = TRACK_NAMES_METRO[2]
            velocity_seq_track = seq.get_track_by_name(velocity_track_name)
            velocity_pad_state = self.metro_seq_pad_state[instrument_short_name][velocity_track_name]
            
            for idx in range(8):
                vel_val = velocity_seq_track[idx * 8]
                for y in range(8):
                    if vel_val == y: 
                        velocity_pad_state[7 - y][idx] = True
                    else:
                        velocity_pad_state[7 - y][idx] = False
            
            # this loop updates all the gate tracks
            gate_track_name = TRACK_NAMES_METRO[3]
            gate_seq_track = seq.get_track_by_name(gate_track_name)
            gate_pad_state = self.metro_seq_pad_state[instrument_short_name][gate_track_name]
            for step_idx, step in enumerate(gate_seq_track):
                step_x = int(step_idx / 8)
                step_y = 7 - step_idx % 8    
                gate_pad_state[step_y][step_x] = step
            
            # this loop updates all the mutes/skips tracks
            mute_skip_track_name = TRACK_NAMES_METRO[4]
            mute_skip_seq_track = seq.get_track_by_name(mute_skip_track_name)
            mute_skip_pad_state = self.metro_seq_pad_state[instrument_short_name][mute_skip_track_name]
            for step_idx, step in enumerate(mute_skip_seq_track):
                step_x = int(step_idx / 8)
                step_y = 7 - step_idx % 8    
                mute_skip_pad_state[step_y][step_x] = step
            
                
            self.update_pads()
            self.app.pads_need_update = True
    
    def load_state(self):
        # pass
        # Loads seq state
        for (
            instrument_short_name
        ) in self.get_all_distinct_instrument_short_names_helper():
            self.instrument_sequencers[instrument_short_name].load_state()

        # Loads Trig edit state
        self.app.trig_edit_mode.load_state()

        # Loads Osc mode state
        self.app.osc_mode.load_state()

        # Loads scale edit menu
        try:
            dump = None
            if os.path.exists(self.scale_menu_filename):
                dump = json.load(open(self.scale_menu_filename))
            for (
                instrument_short_name
            ) in self.get_all_distinct_instrument_short_names_helper():
                for track_name in TRACK_NAMES_METRO:
                    for idx, control in enumerate(
                        self.instrument_scale_edit_controls[instrument_short_name]
                    ):
                        control.value = dump[instrument_short_name][idx]
        except Exception as e:
            print("Exception in trig_edit load_state")
            traceback.print_exc()

    def save_state(self):
        # pass
        # Saves seq state
        scale_edit_state = {}
        try:
            for (
                instrument_short_name
            ) in self.get_all_distinct_instrument_short_names_helper():

                self.instrument_sequencers[instrument_short_name].save_state()
                scale_edit_state[instrument_short_name] = {}
                # Populates the temp scale_edit_state array with current state
                scale_edit_state[instrument_short_name] = [
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ]
                for index, control in enumerate(
                    self.instrument_scale_edit_controls[instrument_short_name]
                ):
                    scale_edit_state[instrument_short_name][index] = control.value
        except Exception as e:
            print("Error in saving scale_edit state")
            traceback.print_exc()
        # Saves scale edit menu
        try:
            json.dump(
                scale_edit_state, open(self.scale_menu_filename, "w")
            )  # Save to file
        except Exception as e:
            print("Exception in trig_edit save_state")
            traceback.print_exc()

        # Saves Trig edit state
        self.app.trig_edit_mode.save_state()

        # Saves Osc mode state
        self.app.osc_mode.save_state()

    def start_timeline(self):
        self.global_timeline.background()

    def stop_timeline(self):
        self.global_timeline.stop()

    def get_settings_to_save(self):
        return {}

    def pad_ij_to_midi_note(self, pad_ij):
        return self.sequencer_pad_matrix[pad_ij[0]][pad_ij[1]]

    def index_to_pad_ij(self, index):
        pad_j = index % 8
        pad_i = 7 - int(index / 8)
        pad_ij = [pad_i, pad_j]
        return pad_ij

    def ij_to_index(self, i, j):
        idx = self.sequencer_pad_matrix[i][j] - 36
        return idx

    def update_octave_buttons(self):
        # Rhythmic does not have octave buttons
        pass

    def sequencer_on_tick(self, instrument_name, length):
        # if seq is active
        
        if self.app.is_mode_active(self.app.metro_sequencer_mode):
            self.update_pads()
            self.app.trig_edit_mode.update_button_colours()
        if self.get_current_instrument_short_name_helper() == instrument_name:
            self.playhead = self.instrument_sequencers[instrument_name].playhead

    def get_all_distinct_instrument_short_names_helper(self):
        return (
            self.app.instrument_selection_mode.get_all_distinct_instrument_short_names()
        )

    def get_current_instrument_short_name_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_short_name()

    def get_current_instrument_osc_port(self):
        return self.app.instrument_selection_mode.get_current_instrument_info()[
            "osc_out_port"
        ]

    def get_current_instrument_color_helper(self):
        return self.app.instrument_selection_mode.get_current_instrument_color()

    def new_instrument_selected(self):
        instrument_index = self.app.instrument_selection_mode.selected_instrument % 8
        instrument_index = int(
            (self.app.instrument_selection_mode.selected_instrument - instrument_index)
            / 8
        )

        self.selected_instrument = TRACK_NAMES_METRO[0]

        device = self.app.osc_mode.get_current_instrument_device()
        device.disable_controls = self.disable_controls
        # print(self.selected_instrument)
        # print(self.app.osc_mode.get_current_instrument_osc_address_sections())

    def set_pitch_for_column(self, i):
        
        # Get pitch pads value
        # get octave
        
        # pitch + 12*octave
        # set pitch in batches of eight to cover for the up to 8 tall gate stacks
        
        pass

    def update_display(self, ctx, w, h):
        if self.show_scale_menu == True:
            background_colour = self.get_current_instrument_color_helper()
            instrument_name = self.get_current_instrument_short_name_helper()
            controls = self.instrument_scale_edit_controls[instrument_name]
        
            # ctx.save()
            ctx.move_to(0, 0)
            ctx.line_to(0, 135)
            ctx.line_to(960, 135)
            ctx.line_to(960, 0)
            ctx.set_source_rgb(255, 0, 0)
            ctx.close_path()
            ctx.fill_preserve()
            offset = 0
            for control in controls:
                control.draw(ctx, offset)
                offset += 1

            # ctx.restore()

    def update_pads(self):
        try:
            instrument_name = self.get_current_instrument_short_name_helper()
            pad_state = self.metro_seq_pad_state[instrument_name]
            seq_pad_state = pad_state[self.selected_track]
            button_colors = [definitions.OFF_BTN_COLOR] * 64
            selected_scale_controls = self.instrument_scale_edit_controls[
                instrument_name
            ]
            track_length = 64
            
            seq = self.instrument_sequencers[instrument_name]
            
            gate_idx = seq.step_index
            gate_idx_x = int(gate_idx / 8)
            gate_idx_y = 7 - gate_idx % 8    
            
            # pitch_and_oct_idx = 
            
            
            for i, value in enumerate(seq_pad_state):
                # Gets the entire row
                for j, value in enumerate(value):
                    idx = i * 8 + j
                    if value:
                        button_colors[idx] = TRACK_COLORS[self.selected_track]

                    # Set pad colours for on/off states of the seq
                    if seq_pad_state[i][j] is True:
                        # If rachet is on display yellow steps
                        
                        if self.rachets[instrument_name][j] == True:
                            button_colors[idx] = definitions.YELLOW

                        # If not display standard blue gates
                        else:
                            button_colors[idx] = TRACK_COLORS[self.selected_track]

                    if self.selected_track != TRACK_NAMES_METRO[3] and (idx % 8) == gate_idx_x:
                        button_colors[idx] = definitions.PINK
                    
                    if seq_pad_state[i][j] == "Off":
                        button_colors[idx] = definitions.OFF_BTN_COLOR

                    if seq_pad_state[i][j] == "Tie":
                        button_colors[idx] = definitions.GREEN_RGB

                    if seq_pad_state[i][j] is False:
                        button_colors[idx] = definitions.BLACK
                    

            if self.selected_track == TRACK_NAMES_METRO[3]:
                # Draw the playhead
                button_colors[gate_idx_y * 8 + gate_idx_x] = definitions.PINK
            # makes the values into a multi-dimensional array
            button_colors_array = []

            while button_colors:
                chunk, button_colors = button_colors[:8], button_colors[8:]
                button_colors_array.append(chunk)

            self.push.pads.set_pads_color(button_colors_array)
        except Exception as exception:
            exception_message = str(exception)
            exception_type, exception_object, exception_traceback = sys.exc_info()
            filename = os.path.split(exception_traceback.tb_frame.f_code.co_filename)[1]

            print(
                f"{exception_message} {exception_type} {filename}, Line {exception_traceback.tb_lineno}"
            )

    def on_pad_pressed(self, pad_n, pad_ij, velocity):
        pad_state = self.metro_seq_pad_state[
            self.get_current_instrument_short_name_helper()
        ]
        idx_n = pad_n - 36
        self.steps_held.append(idx_n)
        seq = self.instrument_sequencers[self.get_current_instrument_short_name_helper()]
        seq_pad_state = pad_state[self.selected_track]
        n = self.steps_held[-1]
        idx_ij = self.index_to_pad_ij(n)
        idx_i = idx_ij[0]
        idx_j = idx_ij[1]
        seq.steps_held.append(idx_j)
        self.disable_controls = True
        # Pitch track
        if self.selected_track == TRACK_NAMES_METRO[0]:
            # One pad
            pitch_value = None
            if len(self.steps_held) == 1:
                # print("Single pad")
                # Turn off all other pads in the column
                for x in range(8):
                    seq_pad_state[x][idx_j] = False
                # If a pad is off, turn it on
                seq_pad_state[idx_i][idx_j] = True
                
                # Set pitch step according to scale
                idx = 7 - idx_i
                pitch_value = self.major_scale[idx]
                
                # If it's on, save the time and cont in on_pad_released
                if seq_pad_state[idx_i][idx_j] == True:
                    self.pads_press_time[idx_n] = time.time()
                    #TODO: call func to show lock here

            # Two pads
            elif len(self.steps_held) == 2:
                # print("two pads")
                step_a_idx = self.steps_held[-1]
                step_a_ij = self.index_to_pad_ij(step_a_idx)
                step_a_i = step_a_ij[0]
                step_a_j = step_a_ij[1]

                step_b_idx = self.steps_held[-2]
                step_b_ij = self.index_to_pad_ij(step_b_idx)
                step_b_i = step_b_ij[0]
                step_b_j = step_b_ij[1]
                
                # For both take the value of the lower step and sharpen it
                pitch_value = self.major_scale[min(7-step_a_i, 7-step_b_i)] + 1
                
                # check pad_i for both to see if they're adjecent
                if abs(step_a_i - step_b_i) == 1:

                    # If either pad if off turn both on
                    if (
                        seq_pad_state[step_a_i][step_a_j] == True
                        or seq_pad_state[step_b_i][step_b_j] == True
                    ):

                        # Turn off all other pads in the column
                        for x in range(8):
                            seq_pad_state[x][idx_j] = False

                        # Turn on target pads
                        seq_pad_state[step_a_i][step_a_j] = True
                        seq_pad_state[step_b_i][step_b_j] = True

                    # if both are on save time and cont in on_pad_released
                    elif (
                        seq_pad_state[step_a_i][step_a_j] == True
                        and seq_pad_state[step_b_i][step_b_j] == True
                    ):
                        self.pads_press_time[step_a_idx] = time.time()
                        self.pads_press_time[step_b_idx] = time.time()

                # if they're not adjecent turn on just the latest one
                if abs(step_a_i - step_b_i) > 1:

                    if seq_pad_state[step_a_i][step_a_j] == False:
                        # Turn off all other pads in the column
                        for x in range(8):
                            seq_pad_state[x][idx_j] = False

                        # Turn on target pads
                        seq_pad_state[step_a_i][step_a_j] = True

                    # If it's on save time and cont in on_pad_released
                    elif seq_pad_state[step_a_i][step_a_j] == False:
                        self.pads_press_time[step_a_idx] = time.time()
                self.app.pads_need_update = True
            elif len(self.steps_held) < 2:
                for idx, step in enumerate(self.steps_held):
                    step_ij = self.index_to_pad_ij(step)
                    # print("Single pad")
                    # Turn off all other pads in the column
                    for x in range(8):
                        step_ij[x][idx_j] = False
                    # If a pad is off, turn it on
                    step_ij[idx_i][idx_j] = True
                    
                    # Set pitch step according to scale
                    idx = 7 - idx_i
                    pitch_value = self.major_scale[idx]
                    
                    # If it's on, save the time and cont in on_pad_released
                    if step_ij[idx_i][idx_j] == True:
                        self.pads_press_time[idx_n] = time.time()
                        #TODO: call func to show lock here
            
            
            # Set the pitches
            for x in range(8):
                seq.set_state([TRACK_NAMES_METRO[0]], idx_j*8 + x, pitch_value)

        # Octaves track
        elif self.selected_track == TRACK_NAMES_METRO[1]:
            # If a pad is off, turn it on
            if seq_pad_state[idx_i][idx_j] == False:
                # Turn off all other pads in the column
                for x in range(8):
                    seq_pad_state[x][idx_j] = False
                seq_pad_state[idx_i][idx_j] = True

            # If it's on, save the time and cont in on_pad_released
            elif seq_pad_state[idx_i][idx_j] == True:
                self.pads_press_time[idx_n] = time.time()
                #TODO: call func to show lock here
            # Set the oct values
            for x in range(8):
                seq.set_state([TRACK_NAMES_METRO[1]], idx_j*8 + x, 7- idx_i)
                    
        # Vel track
        elif self.selected_track == TRACK_NAMES_METRO[2]:
            # If a pad is off, turn it on
            if seq_pad_state[idx_i][idx_j] == False:
                # Turn off all other pads in the column
                for x in range(8):
                    seq_pad_state[x][idx_j] = False
                seq_pad_state[idx_i][idx_j] = True

            # If it's on, save the time and cont in on_pad_released
            elif seq_pad_state[idx_i][idx_j] == True:
                self.pads_press_time[idx_n] = time.time()
                #TODO: call func to show lock here
            # Set the oct values
            for x in range(8):
                seq.set_state([TRACK_NAMES_METRO[2]], idx_j*8 + x, 7- idx_i)

        # Gates track
        elif self.selected_track == TRACK_NAMES_METRO[3]:
            instrument_shortname = self.get_current_instrument_short_name_helper()
            
            # TODO: bug with rachet state logic, needs an empty pad to engage
            rachet_state = self.rachets[instrument_shortname]

            # Make sure pads and right buttons are held,
            # Set rachets on or off
            if len(self.steps_held) != 0: 
                
                # Sets rachet state for the column
                if self.button_1_4t_pressed == True and self.button_1_4_pressed == True:
                    rachet_state[idx_j] = True

                elif self.button_1_4t_pressed == False and self.button_1_4_pressed == True:
                    rachet_state[idx_j] = False
                    
            self.app.pads_need_update = True
            
            # If it's on, save the time and cont in on_pad_released
            if (
                seq_pad_state[idx_i][idx_j] == True
                or seq_pad_state[idx_i][idx_j] == "Tie"
            ):
                if self.button_1_4t_pressed == True and seq_pad_state[idx_i][idx_j] != "Tie":
                    seq_pad_state[idx_i][idx_j] = "Tie"
                else:                        
                    self.pads_press_time[idx_n] = time.time()
                    return
                #TODO: call func to show lock here


            # For normal step edit
            if (
                seq_pad_state[idx_i][idx_j] != True
            ):

                # Turn pad on
                if seq_pad_state[idx_i][idx_j] != False:
                    # for inputing a tie (green pad)
                    if self.button_1_4t_pressed == True:
                        seq_pad_state[idx_i][idx_j] = "Tie"
                    # Normal step
                    else:
                        seq_pad_state[idx_i][idx_j] = True
                        
            # For chaning height of the stack
            if (self.button_1_4_pressed == True):

                # Turn all pads above step black, below grey
                for x in range(8):
                    if x < idx_i:
                        seq_pad_state[x][idx_j] = False
                    if x == idx_i:
                        seq_pad_state[x][idx_j] = True
                    if x > idx_i:
                        # Makes sure we always have pads in off state
                        # While not overriding current state
                        if seq_pad_state[x][idx_j] == False:
                            seq_pad_state[x][idx_j] = "Off"
                        else:
                            pass
            # sets pad state
            for idx_i, i in enumerate(seq_pad_state):
                for idx_j, j in enumerate(i):
                    seq.set_state([TRACK_NAMES_METRO[3]], idx_j*8 + 7 - idx_i, j)
             
        elif self.selected_track == TRACK_NAMES_METRO[4]:
            # If a pad is off
            if seq_pad_state[idx_i][idx_j] == False:
                
                # for skips
                if idx_i == 7: 
                    seq.set_state([TRACK_NAMES_METRO[4]], idx_j*8 + 7- idx_i, True)
                    seq_pad_state[idx_i][idx_j] = True
                # for probability
                else:
                    for x in range(7):
                        seq.set_state([TRACK_NAMES_METRO[4]], idx_j*8 + 7- x, False)
                        seq_pad_state[x][idx_j] = False
                    
                    seq.set_state([TRACK_NAMES_METRO[4]], idx_j*8 + 7- idx_i, True)
                    seq_pad_state[idx_i][idx_j] = True
            # If it's on, save the time and cont in on_pad_released
            elif seq_pad_state[idx_i][idx_j] == True:
                self.pads_press_time[idx_n] = time.time()
                #TODO: call func to show lock here
        
                        
        else:
            # If a pad is off, turn it on
            if seq_pad_state[idx_i][idx_j] == False:
                # Turn off all other pads in the column
                for x in range(8):
                    seq_pad_state[x][idx_j] = False
                    seq.set_state([TRACK_NAMES_METRO[4]], idx_j*8 + x, 7- idx_i)
                seq_pad_state[idx_i][idx_j] = True

            # If it's on, save the time and cont in on_pad_released
            elif seq_pad_state[idx_i][idx_j] == True:
                self.pads_press_time[idx_n] = time.time()
                #TODO: call func to show lock here

        self.app.pads_need_update = True

    def on_pad_released(self, pad_n, pad_ij, velocity):
        pad_state = self.metro_seq_pad_state[
            self.get_current_instrument_short_name_helper()
        ]
        seq_pad_state = pad_state[self.selected_track]
        idx_i = pad_ij[0]
        idx_j = pad_ij[1]
        idx_n = pad_n - 36
        epoch_time = time.time()
        press_time = epoch_time - self.pads_press_time[idx_n]
        seq = self.instrument_sequencers[self.get_current_instrument_short_name_helper()]
        seq.steps_held.remove(idx_j)

        self.disable_controls = False
        if self.selected_track == TRACK_NAMES_METRO[0] or self.selected_track == TRACK_NAMES_METRO[1] or self.selected_track == TRACK_NAMES_METRO[2]:
            pass

        elif self.selected_track == TRACK_NAMES_METRO[3]:
            # Short Press - turn the pad off, reset the timer
            if (
                press_time <= self.pad_quick_press_time
                and self.pads_press_time[idx_n] != False
            ):
                seq_pad_state[idx_i][idx_j] = "Off"
                self.pads_press_time[idx_n] = False
                
                # sets pad state
                for idx_i, i in enumerate(seq_pad_state):
                    for idx_j, j in enumerate(i):
                        seq.set_state([TRACK_NAMES_METRO[3]], idx_j*8 + 7 - idx_i, j)

            # Long Press - keep the pad on, trigger a lock preview
            elif press_time > self.pad_quick_press_time:
                pass
                # seq.set_state(self.selected_track, idx, False

        elif self.selected_track == TRACK_NAMES_METRO[4]:
            # Short press - turn pad off, reset timer
            if (
                press_time <= self.pad_quick_press_time
                and self.pads_press_time[idx_n] != False
            ):
                seq_pad_state[idx_i][idx_j] = False
                self.pads_press_time[idx_n] = False
                seq.set_state([TRACK_NAMES_METRO[4]], idx_j*8 + 7- idx_i,False)

            # Long Press - keep the pad on, trigger a lock preview
            # TODO: trigger a lock preview here
            elif press_time > self.pad_quick_press_time:
                pass
                # seq.set_state(self.selected_track, idx, False

        
        else:
            # Short press - turn pad off, reset timer
            if (
                press_time <= self.pad_quick_press_time
                and self.pads_press_time[idx_n] != False
            ):
                seq_pad_state[idx_i][idx_j] = False
                self.pads_press_time[idx_n] = False

            # Long Press - keep the pad on, trigger a lock preview
            elif press_time > self.pad_quick_press_time:
                pass
                # seq.set_state(self.selected_track, idx, False

        self.steps_held.remove(idx_n)
        self.save_state()
        self.app.pads_need_update = True

    def on_button_pressed(self, button_name):
        seq = self.instrument_sequencers[
            self.get_current_instrument_short_name_helper()
        ]
        if button_name in track_button_names:
            idx = track_button_names.index(button_name)
            self.selected_track = TRACK_NAMES_METRO[idx]
            self.app.trig_edit_mode.update_state()
            self.app.buttons_need_update = True
            self.app.pads_need_update = True

        elif button_name == push2_constants.BUTTON_1_8:
            self.button_1_8_pressed = True

        elif button_name == push2_constants.BUTTON_1_4T:
            self.button_1_4t_pressed = True

        elif button_name == push2_constants.BUTTON_1_4:
            self.button_1_4_pressed = True

        elif (
            button_name == push2_constants.BUTTON_OCTAVE_UP
            or button_name == push2_constants.BUTTON_OCTAVE_DOWN
        ):
            # Don't react to octave up/down buttons as these are not used in rhythm mode
            
            seq = self.instrument_sequencers[self.get_current_instrument_short_name_helper()]
            pass
        elif button_name == push2_constants.BUTTON_DELETE:
            if len(self.steps_held) != 0:
                for step in self.steps_held:
                    seq.clear_all_locks_for_step(step)
        elif button_name == push2_constants.BUTTON_PLAY:
            if self.timeline_is_playing == False:
                self.start_timeline()
                self.timeline_is_playing = True

            elif self.timeline_is_playing == True:
                self.stop_timeline()
                self.timeline_is_playing = False
        elif button_name == push2_constants.BUTTON_SCALE:
            self.disable_controls = True if self.show_scale_menu == False else False
            self.show_scale_menu = True if self.show_scale_menu == False else False

        else:
            # For the other buttons, refer to the base class
            super().on_button_pressed(button_name)

    def on_button_released(self, button_name):
        if button_name == push2_constants.BUTTON_1_8:
            self.button_1_8_pressed = False

        elif button_name == push2_constants.BUTTON_1_4T:
            self.button_1_4t_pressed = False

        elif button_name == push2_constants.BUTTON_1_4:
            self.button_1_4_pressed = False
        else:
            super().on_button_released(button_name)

    def on_encoder_rotated(self, encoder_name, increment):
        try:
            encoder_idx = [
                push2_python.constants.ENCODER_TRACK1_ENCODER,
                push2_python.constants.ENCODER_TRACK2_ENCODER,
                push2_python.constants.ENCODER_TRACK3_ENCODER,
                push2_python.constants.ENCODER_TRACK4_ENCODER,
                push2_python.constants.ENCODER_TRACK5_ENCODER,
                push2_python.constants.ENCODER_TRACK6_ENCODER,
                push2_python.constants.ENCODER_TRACK7_ENCODER,
                push2_python.constants.ENCODER_TRACK8_ENCODER,
            ].index(encoder_name)
            # Check for state of pads here, if pads are being touched, set lock
            seq = self.instrument_sequencers[
                self.get_current_instrument_short_name_helper()
            ]
            self.encoder_incr_since_held[encoder_idx] = True
            try:
                if len(self.steps_held) != 0:
                    device = None
                    for mode in self.app.active_modes:
                        # TODO: We will need to modify this code to make locks work with other devices
                        # TODO: make active page offset the encoder by 8
                        if mode == self.app.trig_edit_mode:
                            device = self.app.trig_edit_mode
                        else:
                            device = self.app.osc_mode.get_current_instrument_device()

                        
                    idx = self.steps_held[0]
                    value = None
                    page_offset = int(device.page) * 8
                    if seq.get_lock_state(idx, encoder_idx + page_offset) == None:
                        value = device.controls[
                            encoder_idx
                        ].value
                    else:
                        # calmping to min/max values, scaling
                        control = device.controls[encoder_idx + page_offset]
                        lock_value = seq.get_lock_state(idx, encoder_idx + page_offset)

                        min = 0 if hasattr(control, "items") else control.min
                        max = (
                            len(control.items)
                            if hasattr(control, "items")
                            else control.max
                        )
                        range = max - min
                        incr = increment * range / 100
                        if lock_value == None:
                            lock_value = control.value
                        if min <= (lock_value + incr) <= max:
                            value = lock_value + incr
                        else:
                            value = lock_value
                    # unindented to cover both branches
                    seq.set_lock_state(idx, encoder_idx + page_offset, value)
                    return
                if self.show_scale_menu == True:
                    # Update scale menu controls
                    instrument_name = self.get_current_instrument_short_name_helper()
                    controls = self.instrument_scale_edit_controls[instrument_name]

                    control = controls[encoder_idx]
                    min = control.min if hasattr(control, "min") else 0
                    max = control.max if hasattr(control, "max") else len(control.items)
                    range = max - min
                    incr = increment * range / 100
                    if min < control.value + incr < max:
                        control.value = control.value + incr
                    if min >= (control.value + incr):
                        control.value = min
                    if max < (control.value + incr):
                        control.value = max - incr

                    self.update_pads()
                self.app.trig_edit_mode.update_button_colours()
            except Exception as e:
                traceback.print_exc()

        except Exception as e:
            traceback.print_exc()
            
    def on_encoder_touched(self, encoder_name):
        try:
            encoder_idx = [
                push2_python.constants.ENCODER_TRACK1_ENCODER,
                push2_python.constants.ENCODER_TRACK2_ENCODER,
                push2_python.constants.ENCODER_TRACK3_ENCODER,
                push2_python.constants.ENCODER_TRACK4_ENCODER,
                push2_python.constants.ENCODER_TRACK5_ENCODER,
                push2_python.constants.ENCODER_TRACK6_ENCODER,
                push2_python.constants.ENCODER_TRACK7_ENCODER,
                push2_python.constants.ENCODER_TRACK8_ENCODER,
            ].index(encoder_name)
            self.encoders_held[encoder_idx] = time.time_ns()
        except ValueError:
            pass
            
    def on_encoder_released(self, encoder_name):
        try:
            encoder_idx = [
                push2_python.constants.ENCODER_TRACK1_ENCODER,
                push2_python.constants.ENCODER_TRACK2_ENCODER,
                push2_python.constants.ENCODER_TRACK3_ENCODER,
                push2_python.constants.ENCODER_TRACK4_ENCODER,
                push2_python.constants.ENCODER_TRACK5_ENCODER,
                push2_python.constants.ENCODER_TRACK6_ENCODER,
                push2_python.constants.ENCODER_TRACK7_ENCODER,
                push2_python.constants.ENCODER_TRACK8_ENCODER,
            ].index(encoder_name)
            if time.time_ns() - self.encoders_held[encoder_idx] < self.encoder_short_press_time:
                if len(self.steps_held) != 0 and self.encoder_incr_since_held[encoder_idx] != True:
                    for step in self.steps_held:
                        seq = self.instrument_sequencers[
                            self.get_current_instrument_short_name_helper()
                        ]

                        device = self.app.osc_mode.get_current_instrument_device()
                        seq.set_lock_state(step, encoder_idx + device.page*8, None)
                        self.encoders_held[encoder_idx] = False
            
            self.encoder_incr_since_held[encoder_idx] = False
        except ValueError:
            pass
