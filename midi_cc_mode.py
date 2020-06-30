import definitions
import mido
import push2_python
import time
import math

from definitions import PyshaMode, OFF_BTN_COLOR, LAYOUT_MELODIC, LAYOUT_RHYTHMIC, PYRAMIDI_CHANNEL
from display_utils import draw_text_at, show_title, show_value, show_text


# TODO: this shoud be loaded from some definition file(s)
synth_midi_control_cc_data = {
    'DDRM': [
        {
            'section': 'GLOBAL',
            'controls': [('BRILL', 109),
                            ('RESSO', 110),
                            ('FEET1', 102),
                            ('FEET2', 103)],
        },{
            'section': 'VCO I',
            'controls': [('SPEED', 40),
                            ('PWM', 41),
                            ('PW', 42)],
        },{
            'section': 'VCO II',
            'controls': [('SPEED', 67),
                            ('PWM', 68),
                            ('PW', 69)],
        }
    ],
    'MINITAUR': [
        {
            'section': 'VCO',
            'controls': [('VCO1 LEV', 15),
                            ('VCO2 LEV', 16)],
        },{
            'section': 'VCF',
            'controls': [('CUTOFF', 19),
                            ('RESSO', 21)],
        },{
            'section': 'LFO',
            'controls': [('VCO AMT', 13),
                            ('VCF AMT', 12)],
        }
    ]
}

class MIDICCControl(object):

    color = definitions.GRAY_LIGHT
    color_rgb = None
    name = 'Unknown'
    section = 'unknown'
    cc_number = 10
    value = 64
    vmin = 0
    vmax = 127
    get_color_func = None
    send_midi_func = None

    def __init__(self, cc_number, name, section_name, get_color_func, send_midi_func):
        self.cc_number = cc_number
        self.name = name
        self.section = section_name
        self.get_color_func = get_color_func
        self.send_midi_func = send_midi_func

    def draw(self, ctx, x_part):
        margin_top = 25
        
        # Param name
        name_height = 20
        show_text(ctx, x_part, margin_top, self.name, height=name_height, font_color=definitions.WHITE)

        # Param value
        val_height = 30
        color = self.get_color_func()
        show_text(ctx, x_part, margin_top + name_height, str(self.value), height=val_height, font_color=color)

        # Knob
        ctx.save()

        circle_break_degrees = 80
        height = 55
        radius = height/2

        display_w = push2_python.constants.DISPLAY_LINE_PIXELS
        x = (display_w // 8) * x_part
        y = margin_top + name_height + val_height + radius + 5
        
        start_rad = (90 + circle_break_degrees // 2) * (math.pi / 180)
        end_rad = (90 - circle_break_degrees // 2) * (math.pi / 180)
        xc = x + radius + 3
        yc = y

        def get_rad_for_value(value):
            total_degrees = 360 - circle_break_degrees
            return start_rad + total_degrees * ((value - self.vmin)/(self.vmax - self.vmin)) * (math.pi / 180)

        # This is needed to prevent showing line from previous position
        ctx.set_source_rgb(0, 0, 0)
        ctx.move_to(xc, yc)
        ctx.stroke()

        # Inner circle
        ctx.arc(xc, yc, radius, start_rad, end_rad)
        ctx.set_source_rgb(*definitions.get_color_rgb_float(definitions.GRAY_LIGHT))
        ctx.set_line_width(1)
        ctx.stroke()

        # Outer circle
        ctx.arc(xc, yc, radius, start_rad, get_rad_for_value(self.value))
        ctx.set_source_rgb(* definitions.get_color_rgb_float(color))
        ctx.set_line_width(3)
        ctx.stroke()

        ctx.restore()
    
    def update_value(self, increment): 
        if self.value + increment > self.vmax:
            self.value = self.vmax
        elif self.value + increment < self.vmin:
            self.value = self.vmin
        else:
            self.value += increment

        msg = mido.Message('control_change', control=self.cc_number, value=self.value)
        self.send_midi_func(msg)


class MIDICCMode(PyshaMode):

    midi_cc_button_names = [
        push2_python.constants.BUTTON_UPPER_ROW_1,
        push2_python.constants.BUTTON_UPPER_ROW_2,
        push2_python.constants.BUTTON_UPPER_ROW_3,
        push2_python.constants.BUTTON_UPPER_ROW_4,
        push2_python.constants.BUTTON_UPPER_ROW_5,
        push2_python.constants.BUTTON_UPPER_ROW_6,
        push2_python.constants.BUTTON_UPPER_ROW_7,
        push2_python.constants.BUTTON_UPPER_ROW_8
    ]
    synth_midi_control_ccs = {}
    active_midi_control_ccs = []
    current_selected_section_and_page = {}

    def initialize(self, settings=None):
        
        get_color_func = self.app.pyramidi_mode.get_current_track_color

        # Create MIDI CC mappings for synths with definitions
        for synth_name, data in synth_midi_control_cc_data.items():
            self.synth_midi_control_ccs[synth_name] = []
            for section in data:
                section_name = section['section']
                for name, cc_number in section['controls']:
                    control = MIDICCControl(cc_number, name, section_name, get_color_func, self.app.send_midi)
                    self.synth_midi_control_ccs[synth_name].append(control)

        # Create MIDI CC mappings for synths without definitions
        for synth_name in self.app.pyramidi_mode.get_all_distinct_instrument_short_names():
            if synth_name not in self.synth_midi_control_ccs:
                self.synth_midi_control_ccs[synth_name] = []
                for i in range(0, 128):
                    section_s = (i // 16) * 16
                    section_e = section_s + 16
                    control = MIDICCControl(i, 'CC {0}'.format(i), '{0} to {1}'.format(section_s, section_e), get_color_func, self.app.send_midi)
                    self.synth_midi_control_ccs[synth_name].append(control)

        # Fill in current page and section variables
        for synth_name in self.synth_midi_control_ccs:
            self.current_selected_section_and_page[synth_name] = (self.synth_midi_control_ccs[synth_name][0].section, 0)

    def get_current_track_midi_cc_sections(self):
        section_names = []
        for control in self.synth_midi_control_ccs.get(self.app.pyramidi_mode.get_current_track_instrument_short_name(), []):
            section_name = control.section
            if section_name not in section_names:
                section_names.append(section_name)
        return section_names

    def get_currently_selected_midi_cc_section_and_page(self):
        return self.current_selected_section_and_page[self.app.pyramidi_mode.get_current_track_instrument_short_name()]

    def get_midi_cc_controls_for_current_track_and_section(self):
        section, _ = self.get_currently_selected_midi_cc_section_and_page()
        return [control for control in self.synth_midi_control_ccs.get(self.app.pyramidi_mode.get_current_track_instrument_short_name(), []) if control.section == section]

    def get_midi_cc_controls_for_current_track_section_and_page(self):
        all_section_controls = self.get_midi_cc_controls_for_current_track_and_section()
        _, page = self.get_currently_selected_midi_cc_section_and_page()
        try:
            return all_section_controls[page * 8:(page+1) * 8]
        except IndexError:
            return []

    def update_current_section_page(self, new_section=None, new_page=None):
        current_section, current_page = self.get_currently_selected_midi_cc_section_and_page()
        result = [current_section, current_page]
        if new_section is not None:
            result[0] = new_section
        if new_page is not None:
            result[1] = new_page
        self.current_selected_section_and_page[self.app.pyramidi_mode.get_current_track_instrument_short_name()] = result
        self.active_midi_control_ccs = self.get_midi_cc_controls_for_current_track_section_and_page()
        self.app.buttons_need_update = True

    def get_should_show_midi_cc_next_prev_pages_for_section(self):
        all_section_controls = self.get_midi_cc_controls_for_current_track_and_section()
        _, page = self.get_currently_selected_midi_cc_section_and_page()
        show_prev = False
        if page > 0:
            show_prev = True
        show_next = False
        if (page + 1) * 8 < len(all_section_controls):
            show_next = True
        return show_prev, show_next

    def new_track_selected(self):
        self.active_midi_control_ccs = self.get_midi_cc_controls_for_current_track_section_and_page()

    def activate(self):
        self.update_buttons()

    def deactivate(self):
        for button_name in self.midi_cc_button_names + [push2_python.constants.BUTTON_PAGE_LEFT, push2_python.constants.BUTTON_PAGE_RIGHT]:
            self.push.buttons.set_button_color(button_name, definitions.BLACK)

    def update_buttons(self):

        n_midi_cc_sections = len(self.get_current_track_midi_cc_sections())
        for count, name in enumerate(self.midi_cc_button_names):
            if count < n_midi_cc_sections:
                self.push.buttons.set_button_color(name, definitions.WHITE)
            else:
                self.push.buttons.set_button_color(name, definitions.OFF_BTN_COLOR)

        show_prev, show_next = self.get_should_show_midi_cc_next_prev_pages_for_section()
        if show_prev:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_LEFT, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_LEFT, definitions.BLACK)
        if show_next:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_RIGHT, definitions.WHITE)
        else:
            self.push.buttons.set_button_color(push2_python.constants.BUTTON_PAGE_RIGHT, definitions.BLACK)

    def update_display(self, ctx, w, h):

        if not self.app.is_mode_active(self.app.settings_mode):
            # If settings mode is active, don't draw the upper parts of the screen because settings page will
            # "cover them"

            # Draw MIDI CCs section names
            section_names = self.get_current_track_midi_cc_sections()[0:8]
            if section_names:
                height = 20
                for i, section_name in enumerate(section_names):
                    show_text(ctx, i, 0, section_name, background_color=definitions.RED)
                    
                    is_selected = False
                    selected_section, _ = self.get_currently_selected_midi_cc_section_and_page()
                    if selected_section == section_name:
                        is_selected = True

                    current_track_color = self.app.pyramidi_mode.get_current_track_color()
                    if is_selected:
                        background_color = current_track_color
                        font_color = definitions.BLACK
                    else:
                        background_color = definitions.BLACK
                        font_color = current_track_color
                    show_text(ctx, i, 0, section_name, height=height,
                            font_color=font_color, background_color=background_color)

            # Draw MIDI CC controls
            if self.active_midi_control_ccs:
                for i in range(0, min(len(self.active_midi_control_ccs), 8)):
                    try:
                        self.active_midi_control_ccs[i].draw(ctx, i)
                    except IndexError:
                        continue
 
    
    def on_button_pressed(self, button_name):
        if  button_name in self.midi_cc_button_names:
            current_track_sections = self.get_current_track_midi_cc_sections()
            n_sections = len(current_track_sections)
            idx = self.midi_cc_button_names.index(button_name)
            if idx < n_sections:
                new_section = current_track_sections[idx]
                self.update_current_section_page(new_section=new_section)
            return True

        elif button_name in [push2_python.constants.BUTTON_PAGE_LEFT, push2_python.constants.BUTTON_PAGE_RIGHT]:
            show_prev, show_next = self.get_should_show_midi_cc_next_prev_pages_for_section()
            _, current_page = self.get_currently_selected_midi_cc_section_and_page()
            if button_name == push2_python.constants.BUTTON_PAGE_LEFT and show_prev:
                self.update_current_section_page(new_page=current_page - 1)
            elif button_name == push2_python.constants.BUTTON_PAGE_RIGHT and show_next:
                self.update_current_section_page(new_page=current_page + 1)
            return True


    def on_encoder_rotated(self, encoder_name, increment):
        try:
            encoder_num = [
                push2_python.constants.ENCODER_TRACK1_ENCODER,
                push2_python.constants.ENCODER_TRACK2_ENCODER,
                push2_python.constants.ENCODER_TRACK3_ENCODER,
                push2_python.constants.ENCODER_TRACK4_ENCODER,
                push2_python.constants.ENCODER_TRACK5_ENCODER,
                push2_python.constants.ENCODER_TRACK6_ENCODER,
                push2_python.constants.ENCODER_TRACK7_ENCODER,
                push2_python.constants.ENCODER_TRACK8_ENCODER,
            ].index(encoder_name)
            if self.active_midi_control_ccs:
                self.active_midi_control_ccs[encoder_num].update_value(increment)
        except ValueError: 
            pass  # Encoder not in list 
        return True  # Always return True because encoder should not be used in any other mode if this is first active