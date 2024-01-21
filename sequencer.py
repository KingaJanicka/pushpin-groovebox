import asyncio
import isobar as iso

default_number_of_steps = 64

class Sequencer(object):
    pitch = 64
    is_running = False
    tick_callback = None

    gates = list() #boolean
    pitch1 = list() #int (midi note)
    pitch2 = list()
    pitch3 = list()
    trig_mute = list() #boolean
    accent = list() #int
    swing = list() #int
    slide = list() #boolean
   
    def __init__(self, instrument_name, timeline, tick_callback):
        self.name = instrument_name
        self.gates = [None] * default_number_of_steps
        self.pitch1 = [self.pitch] * default_number_of_steps
        self.pitch2 = [None] * default_number_of_steps
        self.pitch3 = [None] * default_number_of_steps
        self.trig_mute = [None] * default_number_of_steps
        self.accent = [None] * default_number_of_steps
        self.swing = [None] * default_number_of_steps
        self.slide = [None] * default_number_of_steps
        
        timeline.schedule({
            "action": lambda: tick_callback(self.name, len(self.gates)),
            "duration" : 0.25
        })

     


    def set_states(self, lane, values):
        for index, value in enumerate(values): 
            self.set_state(lane, index, value) 

    def set_state(self, lane, index, value):
        if lane == 'gates':
            self.gates[index] = value
        elif lane == 'pitch1':
            self.pitch1[index] = value
        elif lane == 'pitch2':
            self.pitch2[index] = value
        elif lane == 'pitch3':
            self.pitch3[index] = value
        elif lane == 'trig_mute':
            self.trig_mute[index] = value
        elif lane == 'accent':
            self.accent[index] = value
        elif lane == 'swing':
            self.swing[index] = value
        elif lane == 'slide':
            self.slide[index] = value
        