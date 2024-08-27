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

class Engine(ABC):
    type = None
    PID = None
    pipewireID = None
    pipewire = None
    process = None
    connections = []
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
        self.connections = [self.createLoopback()]
        print(self.connections)
        if self.midi_device_idx == None:
            raise Exception("Midi not init")

    @abstractmethod
    def start(self):
        pass

    def stop(self):
        self.process.kill()

    def createLoopback(self, name="pushpin-loopback", capture_serial=None, playback_serial=None):
        ps = subprocess.Popen(
            [
                "pw-loopback",
                f'-n={name}',
                (f'-C={capture_serial}' if capture_serial else ''),
                (f'-P={playback_serial}' if playback_serial else ''),
            ]
        )
        try:
            while True:
                data = json.loads(
                    subprocess.check_output(["pw-dump", "-N", "Client"])
                    .decode(sys.stdout.encoding)
                    .strip()
                )
        
                return {
                    "config": list(
                        filter(
                            lambda x: x["info"]["props"].get("pipewire.sec.pid") == int(ps.pid),
                            data,
                        )
                    ).pop(),
                    "process": ps,
                }
        except:
            sleep(0.25)

    def setVolume(self, volume):
        setVolumeByPipewireID(pipewire_id=self.pipewireID, volume=volume)

    def connectNodes(self, source_node_id, dest_node_id):
        connectPipewireSourceToPipewireDest(source_id=source_node_id, dest_id=dest_node_id)

    def connectEngineToNode(self, dest_node_id):
        if (not self.pipewireID): raise Exception('Pipewire not instantiated')
        
        source_node_id = self.pipewireID # TODO does this actually take a PWID?
        connectPipewireSourceToPipewireDest(source_id=source_node_id, dest_id=dest_node_id)

    def connectNodeToEngine(self, source_node_id):
        if (not self.pipewireID): raise Exception('Pipewire not instantiated')

        dest_node_id = self.pipewireID # TODO does this actually take a PWID?
        connectPipewireSourceToPipewireDest(source_id=source_node_id, dest_id=dest_node_id)

    def disconnectEngineToNode(self, dest_node_id):
        if (not self.pipewireID): raise Exception('Pipewire not instantiated')
        
        source_node_id = self.pipewireID # TODO does this actually take a PWID?
        disconnectPipewireSourceFromPipewireDest(source_id=source_node_id, dest_id=dest_node_id)

    def disconnectNodeToEngine(self, source_node_id):
        if (not self.pipewireID): raise Exception('Pipewire not instantiated')
        
        dest_node_id = self.pipewireID # TODO does this actually take a PWID?
        disconnectPipewireSourceFromPipewireDest(source_id=source_node_id, dest_id=dest_node_id)



class SurgeXTEngine(Engine):
    def __init__(self, sample_rate=48000, buffer_size=512, midi_device_idx=None):
        super().__init__(
            sample_rate=sample_rate,
            buffer_size=buffer_size,
            midi_device_idx=midi_device_idx,
        )

    def getPID(self):
        return self.PID
    
    def getInstrumentPipewireID(self):
        return self.pipewire['id']

    def getObjectSerial(self):
        return self.pipewire["info"]["props"]["object.serial"]

    def start(self, instrument):
        # self.jack_client = jack.Client(f"Pushpin_{instrument['instrument_short_name']}")

        self.osc_in_port = instrument["osc_in_port"]
        self.osc_out_port = instrument["osc_out_port"]
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
        
        pwConfig = getPipewireConfigForPID(self.PID)
        
        if pwConfig:
            self.pipewire = pwConfig
            self.pipewireID = pwConfig["id"]

            print("_________________________")
            print(self.getObjectSerial())
    
def setVolumeByPipewireID(pipewire_id, volume):
    subprocess.check_output(["pw-cli", "s", pipewire_id, f"Props '{{mute: false, volume:{volume}}}'"]).decode(sys.stdout.encoding).strip()

def connectPipewireSourceToPipewireDest(source_id, dest_id):    
    if not source_id or not dest_id:
        raise Exception('Invalid call to connectPipewireSourcetoPipewireDest()')
    
    subprocess.check_output(["pw-link", source_id, dest_id]).decode(sys.stdout.encoding).strip()

def disconnectPipewireSourceFromPipewireDest(source_id, dest_id):    
    if not source_id or not dest_id:
        raise Exception('Invalid call to disconnectPipewireSourceFromPipewireDest()')
    
    subprocess.check_output(["pw-link","-d", source_id, dest_id]).decode(sys.stdout.encoding).strip()


# Given an engine PID, run pw-dump until the PID shows up and then return that node config
def getPipewireConfigForPID(pid):
    if not pid: raise Exception('No PID provided to getPipewireConfigForPID()')

    while True:
        try:
            data = json.loads(
                subprocess.check_output(["pw-dump", "-N"])
                .decode(sys.stdout.encoding)
                .strip()
            )
            nodes = filter(lambda x: x["type"] == "PipeWire:Interface:Node", data)
            return list(
                filter(
                    lambda x: x["info"]["props"].get("application.process.id")
                    == int(pid),
                    nodes,
                )
            ).pop()
        except:
            sleep(0.25)




def getAllConnectionsToNode(self):
    # this will use     pw-link -l id   command
    # where ID is the pipewire id of the instance you want to know connections of
    # this will list both inputs and outputs
    pass