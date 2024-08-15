from abc import ABC, abstractmethod
import mido
import subprocess


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

        
        self.osc_in_port = instrument['osc_in_port']
        self.osc_out_port = instrument['osc_out_port']
        self.process = subprocess.Popen(
            [
                "surge-xt-cli",
                "--audio-interface=0.5",
                "--audio-input-interface=0.5",
                f"--midi-input={self.midi_device_idx}",
                f"--sample-rate={self.sample_rate}",
                f"--buffer-size={self.buffer_size}",
                f"--osc-in-port={self.osc_in_port}",
                f"--osc-out-port={self.osc_out_port}",
            ]
        )