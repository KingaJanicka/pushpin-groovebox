
import isobar as iso
import time

ticks_per_beat = 24


timeline = iso.Timeline(120, output_device=iso.DummyOutputDevice())
timeline.schedule({
    "action": lambda: print("Hello world")
})
timeline.run()