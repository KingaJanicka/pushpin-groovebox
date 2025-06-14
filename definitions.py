import push2_python
import colorsys
from os import path

VERSION = "0.25"

DELAYED_ACTIONS_APPLY_TIME = (
    1.0  # Encoder changes won't be applied until this time has passed since last moved
)

LAYOUT_MELODIC = "lmelodic"
LAYOUT_RHYTHMIC = "lrhythmic"
LAYOUT_SLICES = "lslices"
LAYOUT_SEQUENCER = "lseq"
NOTIFICATION_TIME = 3

BLACK_RGB = [0, 0, 0]
GRAY_DARK_RGB = [30, 30, 30]
GRAY_LIGHT_RGB = [180, 180, 180]
WHITE_RGB = [255, 255, 255]
YELLOW_RGB = [255, 241, 0]
ORANGE_RGB = [255, 140, 0]
RED_RGB = [232, 17, 35]
PINK_RGB = [236, 0, 140]
PURPLE_RGB = [104, 33, 122]
BLUE_RGB = [0, 24, 143]
CYAN_RGB = [0, 188, 242]
TURQUOISE_RGB = [0, 178, 148]
GREEN_RGB = [0, 158, 73]
LIME_RGB = [186, 216, 10]

BLACK = "black"
GRAY_DARK = "gray_dark"
GRAY_LIGHT = "gray_light"
WHITE = "white"
YELLOW = "yellow"
ORANGE = "orange"
RED = "red"
PINK = "pink"
PURPLE = "purple"
BLUE = "blue"
CYAN = "cyan"
TURQUOISE = "turquoise"
GREEN = "green"
LIME = "lime"

COLORS_NAMES = [
    ORANGE,
    YELLOW,
    TURQUOISE,
    LIME,
    RED,
    PINK,
    PURPLE,
    BLUE,
    CYAN,
    GREEN,
    BLACK,
    GRAY_DARK,
    GRAY_LIGHT,
    WHITE,
]


def get_color_rgb(color_name):
    return globals().get("{0}_RGB".format(color_name.upper()), [0, 0, 0])


def get_color_rgb_float(color_name):
    return [x / 255 for x in get_color_rgb(color_name)]


# Create darker1 and darker2 versions of each color in COLOR_NAMES, add new colors back to COLOR_NAMES
to_add_in_color_names = []
for name in COLORS_NAMES:

    # Create darker 1
    color_mod = 0.35  # < 1 means make colour darker, > 1 means make colour brighter
    c = colorsys.rgb_to_hls(*get_color_rgb_float(name))
    darker_color = colorsys.hls_to_rgb(c[0], max(0, min(1, color_mod * c[1])), c[2])
    new_color_name = f"{name}_darker1"
    globals()[new_color_name.upper()] = new_color_name
    if new_color_name not in COLORS_NAMES:
        to_add_in_color_names.append(new_color_name)
    new_color_rgb_name = f"{name}_darker1_rgb"
    globals()[new_color_rgb_name.upper()] = list([c * 255 for c in darker_color])

    # Create darker 2
    color_mod = 0.05  # < 1 means make colour darker, > 1 means make colour brighter
    c = colorsys.rgb_to_hls(*get_color_rgb_float(name))
    darker_color = colorsys.hls_to_rgb(c[0], max(0, min(1, color_mod * c[1])), c[2])
    new_color_name = f"{name}_darker2"
    globals()[new_color_name.upper()] = new_color_name
    if new_color_name not in COLORS_NAMES:
        to_add_in_color_names.append(new_color_name)
    new_color_rgb_name = f"{name}_darker2_rgb"
    globals()[new_color_rgb_name.upper()] = list([c * 255 for c in darker_color])

COLORS_NAMES += to_add_in_color_names  # Update list of color names with darkified versiond of existing colors

FONT_COLOR_DELAYED_ACTIONS = ORANGE
FONT_COLOR_DISABLED = GRAY_LIGHT
OFF_BTN_COLOR = GRAY_DARK
NOTE_ON_COLOR = GREEN

DEFAULT_ANIMATION = push2_python.constants.ANIMATION_PULSING_QUARTER
DEFINITIONS_FOLDER = "definitions"
INSTRUMENT_DEFINITION_FOLDER = DEFINITIONS_FOLDER +"/"+"instrument_definitions"
DEVICE_DEFINITION_FOLDER = DEFINITIONS_FOLDER +"/"+"device_definitions"
EFFECT_DEFINITION_FOLDER = DEFINITIONS_FOLDER +"/"+"effect_definitions"
MODULATION_DEFINITIONS_FOLDER = DEFINITIONS_FOLDER +"/"+"modulation_definitions"
INSTRUMENT_LISTING_PATH = "definitions/instrument_listing.json"
SURGE_XT_ROOT = (
    f"{path.expanduser('~')}/.local/share/surge-xt"
    if path.isdir(f"{path.expanduser('~')}/.local/share/surge-xt")
    else "/usr/share/surge-xt"
)
FACTORY_PATCHES_FOLDER = f"{SURGE_XT_ROOT}/patches_factory"
THIRD_PARTY_PATCHES_FOLDER = f"{SURGE_XT_ROOT}/patches_3rdparty"
USER_PATCHES_FOLDER = f"{path.expanduser('~')}/Documents/Surge XT/Patches"
TRACK_NAMES = [
    "gate_1",
    "pitch_1",
    "trig_mute_1",
    "accent_1",
    "aux_1",
    "aux_2",
    "aux_3",
    "aux_4",
]

TRACK_NAMES_METRO = [
    "pitch",
    "octave",
    "gate",
    "accent_1",
    "aux_1",
    "aux_2",
    "aux_3",
    "aux_4",
]

DEFAULT_GLOBAL_TEMPO = 120


class PyshaMode(object):
    """ """

    name = ""
    xor_group = None

    def __init__(self, app, settings=None):
        self.app = app
        self.initialize(settings=settings)

    @property
    def push(self):
        return self.app.push

    # Method run only once when the mode object is created, may receive settings dictionary from main app
    def initialize(self, settings=None):
        pass

    # Method to return a dictionary of properties to store in a settings file, and that will be passed to
    # initialize method when object created
    def get_settings_to_save(self):
        return {}

    # Methods that are run before the mode is activated and when it is deactivated
    def activate(self):
        pass

    def deactivate(self):
        pass

    # Method called at every iteration in the main loop to see if any actions need to be performed at the end of the iteration
    # This is used to avoid some actions unncessesarily being repeated many times
    def check_for_delayed_actions(self):
        pass

    # Method called when MIDI messages arrive from Pysha MIDI input
    def on_midi_in(self, msg, source=None):
        pass

    # Push2 update methods
    def update_pads(self):
        pass

    def update_buttons(self):
        pass

    def update_display(self, ctx, w, h):
        pass

    # Push2 action callbacks (these methods should return True if some action was carried out, otherwise return None)
    def on_encoder_rotated(self, encoder_name, increment):
        pass

    def on_encoder_touched(self, encoder_name):
        pass

    def on_button_pressed(self, button_name):
        pass

    def on_button_released(self, button_name):
        pass

    def on_pad_pressed(self, pad_n, pad_ij, velocity):
        pass

    def on_pad_released(self, pad_n, pad_ij, velocity):
        pass

    def on_pad_aftertouch(self, pad_n, pad_ij, velocity):
        pass

    def on_touchstrip(self, value):
        pass

    def on_sustain_pedal(self, sustain_on):
        pass
