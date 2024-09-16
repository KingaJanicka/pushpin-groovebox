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
    pw_ports = None
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
        self.pw_ports = {"input": [], "output": []}
        if self.midi_device_idx == None:
            raise Exception("Midi not init")

    async def start(self):
        # self.connections.append(await self.createLoopback())
        pass
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

    async def get_instrument_nodes(self):
        nodes = await getAllNodes()
        instrument_nodes = []      

        for node in nodes:
                if node.get("info",{}).get("props",{}).get("application.process.id", None) == (self.PID):
                    instrument_nodes.append(node)

        return instrument_nodes


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
        
        self.process = await asyncio.create_subprocess_exec(
            f"surge-xt-cli",
            f"--audio-interface={'0.0'}",f"--audio-input-interface={'0.0'}", f"--midi-input={self.midi_device_idx}", f"--sample-rate={self.sample_rate}", f"--buffer-size={self.buffer_size}", f"--osc-in-port={self.osc_in_port}", f"--osc-out-port={self.osc_out_port}",
            # stdin=asyncio.subprocess.PIPE,
            # stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.STDOUT
            
        )

        self.PID = self.process.pid
        
        # Sleep 2s to allow Surge boot up
        await asyncio.sleep(2) 

        all_ports = await getAllPorts()
        instrument_nodes = await self.get_instrument_nodes()
        print("Engine stuff", " PID: ", self.PID)
        for port in all_ports:
            # with nodes we can associate nodes with clients/instruments via PID
            # And ports with nodes via ID/node.id
            # With those IDs in place we can start calling pw-link
            
            #TODO: there is a bug in this function where it will give all of the ports to all instruments
            
            for instrument_node in instrument_nodes:
                # print(instrument_node.get("id", None), port.get("info",{}).get("props", {}).get("node.id", None))
                if port.get("info",{}).get("props", {}).get("node.id", None) == instrument_node.get("id", None):
                    # print("ID correct", instrument_node.get("id", None))
                    if port.get("info",{}).get("direction",None):
                        if "output" in port.get("info", []).get("props",[]).get("port.name","None"):
                            self.pw_ports["output"].append(port)
                        elif "input" in port.get("info", []).get("props",[]).get("port.name","None"):
                            self.pw_ports["input"].append(port)

        for port in self.pw_ports["input"]:
            print(port["id"])
        # print("in ports: ", len(self.pw_ports["input"]))
        # print("out ports: ", len(self.pw_ports["output"]))



    async def updateConfig(self):
        self.PID = self.process.pid
        pwConfig = await getPipewireConfigForPID(self.PID)
        if pwConfig:
            self.pipewire = pwConfig
            self.pipewireID = pwConfig["id"]




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
    
    try:
        cmd = f"pw-link {str(source_id)} {str(dest_id)}"
        print(cmd)
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except Exception as e:
        print("Error in connectPipewireSourceToPipewireDest")
        print(e)
    stdout, stderr = await proc.communicate()

    if stdout:
        print(stdout.decode().strip())
    elif stderr:
        print(stderr.decode().strip())
        
async def disconnectPipewireSourceFromPipewireDest(source_id, dest_id):    
    if not source_id or not dest_id:
        raise Exception('Invalid call to disconnectPipewireSourceFromPipewireDest()')
    
    proc = await asyncio.create_subprocess_shell(f"pw-link -d {str(source_id)} {str(dest_id)}", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()

    if stdout:
        print(stdout.decode().strip())
    elif stderr:
        print(stderr.decode().strip())

# Given an engine PID, run pw-dump until the PID shows up and then return that node config
async def getPipewireConfigForPID(pid):
    if not pid: raise Exception('No PID provided to getPipewireConfigForPID()')
    i=0
    while True:
        try:
            proc = await asyncio.create_subprocess_shell("pw-dump -N Node", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            if stdout:
                data = json.loads(
                    stdout.decode().strip()
                )
                # nodes = filter(lambda x: x["info"]["n-input-ports"] == 0, data)
                input_node, output_node = list(
                    filter(
                        lambda x: x["info"]["props"].get("application.process.id")
                        == int(pid),
                        # nodes,
                    )
                ).sort(key=lambda x: x["info"]["n-input-ports"], reverse=True)
                return {"input": input_node, "output": output_node}
        except:
            i += 1
            if i >= 10:
                raise Exception("GetPipewireConfigForPid unable to get nodes")
            await asyncio.sleep(0.25)


async def getAllClients():
  
    proc = await asyncio.create_subprocess_shell("pw-dump -N Client", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if stdout:
        data = json.loads(
            stdout.decode().strip()
        )
        return data
        
async def getAllNodes():
    proc = await asyncio.create_subprocess_shell("pw-dump -N Node", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    data = []
    if stderr:
        print('getAllNodes ERROR:')
        print(stderr)
    if stdout:
        try:
            data = json.loads(
                stdout.decode().strip()
            )
        except Exception as e:
            print(e)
            # print(stdout)
    return data

async def getAllPorts():
    proc = await asyncio.create_subprocess_shell("pw-dump -N Port", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()

    if stderr:
        print(stderr.decode())

    if stdout:
        data = json.loads(
            stdout.decode().strip()
        )
        return data
            



def getAllConnectionsToNode(self):
    # this will use     pw-link -l id   command
    # where ID is the pipewire id of the instance you want to know connections of
    # this will list both inputs and outputs
    pass



### Connect using pw-cli create-link <pipewire-id> <port-id> <pipewire-id> <port-id>

### Conenct using PW-Link pw-link <port "id"> <port "id">  
### get port IDs with pw-dump Port
### ensure which surge instance is which with object.id