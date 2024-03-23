import definitions


class ControlSpacer(object):
    name = "Spacer"

    address = None
    active = True
    label = None
    size = 1
    color = definitions.GRAY_LIGHT
    color_rgb = None
    label = ""
    get_color_func = None

    def __init__(self):
        pass

    def draw(self, *args, **kwargs):
        pass

    def update_value(self, *args, **kwargs):
        pass
