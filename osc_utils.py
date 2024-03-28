def scale_knob_value(value, minimum, maximum):
    return float(value) * (float(maximum) - float(minimum)) / 127


def scale_osc_value(value, minimum, maximum):
    return (value - minimum) * (127 / (maximum - minimum))
