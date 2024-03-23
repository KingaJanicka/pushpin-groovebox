class OSCMenuItem(object):
    name = "Menu Item"

    def __init__(self, config, get_color_func=None, send_osc_func=None):
        if config.get("$type", None) != "menu-item":
            raise Exception("Invalid config passed to new OSCMenuItem")

        self.label = config.get("label", "")
        self.message = config.get("onselect", None)
        self.get_color_func = get_color_func
        self.send_osc_func = send_osc_func

    def select(self):
        self.send_osc_func(self.message["address"], self.message["value"])
