import asyncio
import isobar as iso

class Sequencer(object):
    number_of_steps = 64
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
   
    def __init__(self):
    
        self.gates = [None] * self.number_of_steps
        self.pitch1 = [self.pitch] * self.number_of_steps
        self.pitch2 = [None] * self.number_of_steps
        self.pitch3 = [None] * self.number_of_steps
        self.trig_mute = [None] * self.number_of_steps
        self.accent = [None] * self.number_of_steps
        self.swing = [None] * self.number_of_steps
        self.slide = [None] * self.number_of_steps
        self.timeline = iso.Timeline(120, output_device=iso.DummyOutputDevice())
        self.timeline.schedule({
            "action": lambda: self.tick_callback(self.gates)
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
        
    def start(self, tick_callback):
        self.tick_callback = tick_callback
        self.is_running = True
        self.timeline.background()
        # asyncio.run(self.tick())


    def stop(self):
        self.is_running = False
        self.timeline.stop()

    def tick(self):
        if self.is_running:
            # await asyncio.sleep(0.1)
            if self.tick_callback:
                self.tick_callback(self.gates)
            print("tick")
            # await self.tick()