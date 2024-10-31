
import isobar as iso
import time

ticks_per_beat = 24


osc_device = iso.OSCOutputDevice("127.0.0.1", 1030)
timeline = iso.Timeline(120, output_device=osc_device)
timeline.schedule({
    "osc_address": "/param/a/osc/1/pitch",
    "osc_params": [ iso.PSequence([ 0.5, 0.8 ]) ],
})
print("BLA")
timeline.run()