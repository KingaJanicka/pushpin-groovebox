from abc import ABC
import asyncio

import re
import sys
import json

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
    instrument = None

    def __init__(self, sample_rate=48000, buffer_size=512, midi_device_idx=None, instrument_definition=None):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.midi_device_idx = midi_device_idx
        self.connections = []
        self.instrument = instrument_definition

        if self.midi_device_idx == None:
            raise Exception("Midi not init")

    async def start(self):
        self.connections.append(await self.createLoopback())

    def stop(self):
        self.process.kill()

    async def createLoopback(self, name="pushpin-loopback", capture_serial=None, playback_serial=None):
        ps = await asyncio.create_subprocess_shell(
            f"pw-loopback -n={name} -C={capture_serial if capture_serial else ''} -P={playback_serial if playback_serial else ''}"
        )
        try:
            while True:
                proc = await asyncio.create_subprocess_shell("pw-dump -N Client", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await proc.communicate()
                if stderr:
                    print('Error!', stderr.decode())
                elif stdout:
                    data = json.loads(
                        stdout
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
            await asyncio.sleep(0.25)

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
    def __init__(self, sample_rate=48000, buffer_size=512, midi_device_idx=None, instrument_definition=None):
        super().__init__(
            sample_rate=sample_rate,
            buffer_size=buffer_size,
            midi_device_idx=midi_device_idx,
            instrument_definition=instrument_definition
        )

    def getPID(self):
        return self.PID
    
    def getInstrumentPipewireID(self):
        return self.pipewire['id']

    def getObjectSerial(self):
        return self.pipewire["info"]["props"]["object.serial"]

    async def start(self):
        # self.jack_client = jack.Client(f"Pushpin_{instrument['instrument_short_name']}")
        await super().start()

        self.osc_in_port = self.instrument["osc_in_port"]
        self.osc_out_port = self.instrument["osc_out_port"]
        print('SURGE')
        
        self.process = await asyncio.create_subprocess_shell(
            f"/pushpin/surge/build/surge_xt_products/surge-xt-cli --audio-interface={'0.0'} --midi-input={self.midi_device_idx} --sample-rate={self.sample_rate} --buffer-size={self.buffer_size} --osc-in-port={self.osc_in_port} --osc-out-port={self.osc_out_port}",
            # stdin=asyncio.subprocess.PIPE,
            # stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.STDOUT
        )
        # self.PID = self.process.pid
        
        # # pwConfig = await getPipewireConfigForPID(self.PID)
        
        # # if pwConfig:
        # #     self.pipewire = pwConfig
        # #     self.pipewireID = pwConfig["id"]

        # #     print("_________________________")
        # #     print(await self.getObjectSerial())
        # # print('waht')
        await self.process.wait()
        print(asyncio.subprocess.STDOUT)
        print(asyncio.subprocess.PIPE)
async def setVolumeByPipewireID(pipewire_id, volume):
    proc = await asyncio.create_subprocess_shell(["pw-cli", "s", pipewire_id, f"Props '{{mute: false, volume:{volume}}}'"], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    
    stdout, stderr = await proc.communicate()

    if stdout:
        print(stdout.decode().strip())
    elif stderr:
        print(stderr.decode().strip())

async def connectPipewireSourceToPipewireDest(source_id, dest_id):    
    if not source_id or not dest_id:
        raise Exception('Invalid call to connectPipewireSourcetoPipewireDest()')
    
    proc = await asyncio.create_subprocess_shell(["pw-link", source_id, dest_id], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()

    if stdout:
        print(stdout.decode().strip())
    elif stderr:
        print(stderr.decode().strip())
async def disconnectPipewireSourceFromPipewireDest(source_id, dest_id):    
    if not source_id or not dest_id:
        raise Exception('Invalid call to disconnectPipewireSourceFromPipewireDest()')
    
    proc = await asyncio.create_subprocess_shell(["pw-link","-d", source_id, dest_id], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()

    if stdout:
        print(stdout.decode().strip())
    elif stderr:
        print(stderr.decode().strip())

# Given an engine PID, run pw-dump until the PID shows up and then return that node config
async def getPipewireConfigForPID(pid):
    if not pid: raise Exception('No PID provided to getPipewireConfigForPID()')

    while True:
        try:
            proc = await asyncio.create_subprocess_shell("pw-dump -N", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            if stdout:
                data = json.loads(
                    stdout.decode().strip()
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
            await asyncio.sleep(0.25)



def getAllConnectionsToNode(self):
    # this will use     pw-link -l id   command
    # where ID is the pipewire id of the instance you want to know connections of
    # this will list both inputs and outputs
    pass