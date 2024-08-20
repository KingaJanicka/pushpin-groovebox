from abc import ABC, abstractmethod
import subprocess
# import jack
import re
import sys
import json
from time import sleep
# JACK_INTERFACE = None

# def getJackInterface():
#     global JACK_INTERFACE
#     if JACK_INTERFACE == None:
#         surge_devices = subprocess.check_output(['surge-xt-cli', '-l']).decode(sys.stdout.encoding).strip()
#         groups = re.search(r"\[(\d+\.\d+)\] : ALSA\.JACK Audio Connection Kit", surge_devices).groups()
#         if groups:
#             JACK_INTERFACE = groups[0]
#         else:
#             print("jackd not running; starting...")
#             subprocess.Popen(['jack_control', 'start'])
#             getJackInterface()
        
# getJackInterface()

# Given an engine PID, run pw-dump until the PID shows up and then return that node config
def getEnginePipewireConfig(pid):
    while True:
        try:
            data = json.loads(subprocess.check_output(['pw-dump', '-N']).decode(sys.stdout.encoding).strip())
            nodes = filter(lambda x: x['type'] == 'PipeWire:Interface:Node', data)
            return list(filter(lambda x:  x['info']['props'].get('application.process.id') == int(pid), nodes)).pop()
        except:
            sleep(.25)
        

class Engine(ABC):
    type = None
    PID = None
    process = None
    sample_rate = 48000
    buffer_size = 512
    midi_in_port = None
    midi_out_port = None
    midi_port = None
    midi_device_idx = None
    osc_in_port = None
    osc_out_port = None
    jack_client = None

    def __init__(self, sample_rate=48000, buffer_size=512, midi_device_idx=None):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.midi_device_idx = midi_device_idx
        
        if self.midi_device_idx == None:
            raise Exception("Midi not init")
     
    @abstractmethod
    def start(self):
        pass
    
    def stop(self):
        self.process.kill()
    
    
class SurgeXTEngine(Engine):
    def __init__(self, sample_rate=48000, buffer_size=512, midi_device_idx=None):
        super().__init__(sample_rate=sample_rate, buffer_size=buffer_size, midi_device_idx=midi_device_idx)
        

    def start(self, instrument):
        # self.jack_client = jack.Client(f"Pushpin_{instrument['instrument_short_name']}")

        self.osc_in_port = instrument['osc_in_port']
        self.osc_out_port = instrument['osc_out_port']
        self.process = subprocess.Popen(
            [
                "surge-xt-cli",
                f"--audio-interface={'0.0'}",
                f"--audio-input-interface={'0.0'}",
                f"--midi-input={self.midi_device_idx}",
                f"--sample-rate={self.sample_rate}",
                f"--buffer-size={self.buffer_size}",
                f"--osc-in-port={self.osc_in_port}",
                f"--osc-out-port={self.osc_out_port}",
            ]
        )
        self.PID = self.process.pid
        
        pwConfig = getEnginePipewireConfig(self.PID)
        if pwConfig:
            self.pipewire = pwConfig
            print(pwConfig)