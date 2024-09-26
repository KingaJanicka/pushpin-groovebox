from abc import ABC
import asyncio

import sys
import json
from signal import SIGINT


class Engine(ABC):
    type = None
    PID = None
    pipewireID = None
    pipewire = None
    process = None
    instrument_nodes = None
    connections = None
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
    duplex_node = None
    duplex_ports = None

    def __init__(
        self,
        sample_rate=48000,
        buffer_size=512,
        midi_device_idx=None,
        instrument_definition=None,
    ):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.midi_device_idx = midi_device_idx
        self.instrument = instrument_definition
        self.duplex_node = None
        self.duplex_ports = {
            "inputs": {
                "Input 0": {"L": None, "R": None},
                "Input 1": {"L": None, "R": None},
                "Input 2": {"L": None, "R": None},
                "Input 3": {"L": None, "R": None},
                "Input 4": {"L": None, "R": None},
                "Input 5": {"L": None, "R": None},
                "Input 6": {"L": None, "R": None},
                "Input 7": {"L": None, "R": None},
            },
            "outputs": {
                "Output 0": {"L": None, "R": None},
                "Output 1": {"L": None, "R": None},
                "Output 2": {"L": None, "R": None},
                "Output 3": {"L": None, "R": None},
                "Output 4": {"L": None, "R": None},
                "Output 5": {"L": None, "R": None},
                "Output 6": {"L": None, "R": None},
                "Output 7": {"L": None, "R": None},
            },
        }
        self.pw_ports = {"input": [], "output": []}
        # This needs to be spelled out like that because otherwise they all behave as one and you can't assign different values to dicts
        self.connections = [
            {"L": None, "R": None},
            {"L": None, "R": None},
            {"L": None, "R": None},
            {"L": None, "R": None},
            {"L": None, "R": None},
            {"L": None, "R": None},
            {"L": None, "R": None},
            {"L": None, "R": None},
        ]
        if self.midi_device_idx == None:
            raise Exception("Midi not init")

    async def start(self):
        # self.connections.append(await self.createLoopback())
        pass

    def stop(self):
        self.process.kill()

    def setVolume(self, volume):
        setVolumeByPipewireID(pipewire_id=self.pipewireID, volume=volume)

    def connectNodes(self, source_node_id, dest_node_id):
        connectPipewireSourceToPipewireDest(
            source_id=source_node_id, dest_id=dest_node_id
        )

    def connectEngineToNode(self, dest_node_id):
        if not self.pipewireID:
            raise Exception("Pipewire not instantiated")

        source_node_id = self.pipewireID  # TODO does this actually take a PWID?
        connectPipewireSourceToPipewireDest(
            source_id=source_node_id, dest_id=dest_node_id
        )

    def connectNodeToEngine(self, source_node_id):
        if not self.pipewireID:
            raise Exception("Pipewire not instantiated")

        dest_node_id = self.pipewireID  # TODO does this actually take a PWID?
        connectPipewireSourceToPipewireDest(
            source_id=source_node_id, dest_id=dest_node_id
        )

    def disconnectEngineToNode(self, dest_node_id):
        if not self.pipewireID:
            raise Exception("Pipewire not instantiated")

        source_node_id = self.pipewireID  # TODO does this actually take a PWID?
        disconnectPipewireSourceFromPipewireDest(
            source_id=source_node_id, dest_id=dest_node_id
        )

    def disconnectNodeToEngine(self, source_node_id):
        if not self.pipewireID:
            raise Exception("Pipewire not instantiated")

        dest_node_id = self.pipewireID  # TODO does this actually take a PWID?
        disconnectPipewireSourceFromPipewireDest(
            source_id=source_node_id, dest_id=dest_node_id
        )

    async def get_instrument_nodes(self):
        nodes = await getAllNodes()
        instrument_nodes = []

        for node in nodes:
            if node.get("info", {}).get("props", {}).get(
                "application.process.id", None
            ) == (self.PID):
                instrument_nodes.append(node)

        return instrument_nodes

    async def get_instrument_duplex_node(self):
        nodes = await getAllNodes()
        # Gets the right node, so we can adjust volumes and get the ID for ports
        for node in nodes:
            #TODO: we need to have less jank way of matching this
            if node.get("info", []).get("props", []).get("node.description",None) == self.instrument["instrument_name"]:
                self.duplex_node = node
                return node
            
    async def get_instrument_duplex_ports(self):
        ports = await getAllPorts()
        unsorted_duplex_ports = []

        for port in ports:
            if port["info"]["props"]["node.id"] == self.duplex_node["id"]:
                unsorted_duplex_ports.append(port)

        for port in unsorted_duplex_ports:
            #TODO: this name will need to change once we get the aux stuff to display corretly
            #TODO: this match be UGGLY
            match port["info"]["props"]["port.name"]:
                case "playback_1":
                    self.duplex_ports["inputs"]["Input 0"]["L"] = port
                case "playback_2":
                    self.duplex_ports["inputs"]["Input 0"]["R"] = port
                case "playback_3":
                    self.duplex_ports["inputs"]["Input 1"]["L"] = port
                case "playback_4":
                    self.duplex_ports["inputs"]["Input 1"]["R"] = port
                case "playback_5":
                    self.duplex_ports["inputs"]["Input 2"]["L"] = port
                case "playback_6":
                    self.duplex_ports["inputs"]["Input 2"]["R"] = port
                case "playback_7":
                    self.duplex_ports["inputs"]["Input 3"]["L"] = port
                case "playback_8":
                    self.duplex_ports["inputs"]["Input 3"]["R"] = port
                case "playback_9":
                    self.duplex_ports["inputs"]["Input 4"]["L"] = port
                case "playback_10":
                    self.duplex_ports["inputs"]["Input 4"]["R"] = port
                case "playback_11":
                    self.duplex_ports["inputs"]["Input 5"]["L"] = port
                case "playback_12":
                    self.duplex_ports["inputs"]["Input 5"]["R"] = port
                case "playback_13":
                    self.duplex_ports["inputs"]["Input 6"]["L"] = port
                case "playback_14":
                    self.duplex_ports["inputs"]["Input 6"]["R"] = port
                case "playback_15":
                    self.duplex_ports["inputs"]["Input 7"]["L"] = port
                case "playback_16":
                    self.duplex_ports["inputs"]["Input 7"]["R"] = port
                case "capture_1":
                    self.duplex_ports["outputs"]["Output 0"]["L"] = port
                case "capture_2":
                    self.duplex_ports["outputs"]["Output 0"]["R"] = port
                case "capture_3":
                    self.duplex_ports["outputs"]["Output 1"]["L"] = port
                case "capture_4":
                    self.duplex_ports["outputs"]["Output 1"]["R"] = port
                case "capture_5":
                    self.duplex_ports["outputs"]["Output 2"]["L"] = port
                case "capture_6":
                    self.duplex_ports["outputs"]["Output 2"]["R"] = port
                case "capture_7":
                    self.duplex_ports["outputs"]["Output 3"]["L"] = port
                case "capture_8":
                    self.duplex_ports["outputs"]["Output 3"]["R"] = port
                case "capture_9":
                    self.duplex_ports["outputs"]["Output 4"]["L"] = port
                case "capture_10":
                    self.duplex_ports["outputs"]["Output 4"]["R"] = port
                case "capture_11":
                    self.duplex_ports["outputs"]["Output 5"]["L"] = port
                case "capture_12":
                    self.duplex_ports["outputs"]["Output 5"]["R"] = port
                case "capture_13":
                    self.duplex_ports["outputs"]["Output 6"]["L"] = port
                case "capture_14":
                    self.duplex_ports["outputs"]["Output 6"]["R"] = port
                case "capture_15":
                    self.duplex_ports["outputs"]["Output 7"]["L"] = port
                case "capture_16":
                    self.duplex_ports["outputs"]["Output 7"]["R"] = port
                case _:
                    pass


class SurgeXTEngine(Engine):
    def __init__(
        self,
        sample_rate=48000,
        buffer_size=512,
        midi_device_idx=None,
        instrument_definition=None,
    ):
        super().__init__(
            sample_rate=sample_rate,
            buffer_size=buffer_size,
            midi_device_idx=midi_device_idx,
            instrument_definition=instrument_definition,
        )

    def getPID(self):
        return self.PID

    def getInstrumentPipewireID(self):
        return self.pipewire["id"]

    def getObjectSerial(self):
        return self.pipewire["info"]["props"]["object.serial"]

    async def start(self):
        # self.jack_client = jack.Client(f"Pushpin_{instrument['instrument_short_name']}")
        await super().start()

        self.osc_in_port = self.instrument["osc_in_port"]
        self.osc_out_port = self.instrument["osc_out_port"]

        self.process = await asyncio.create_subprocess_exec(
            f"surge-xt-cli",
            f"--audio-interface={'0.0'}",
            f"--audio-input-interface={'0.0'}",
            f"--midi-input={self.midi_device_idx}",
            f"--sample-rate={self.sample_rate}",
            f"--buffer-size={self.buffer_size}",
            f"--osc-in-port={self.osc_in_port}",
            f"--osc-out-port={self.osc_out_port}",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self.PID = self.process.pid

        # Sleep 2s to allow Surge boot up
        await asyncio.sleep(2)

        all_ports = await getAllPorts()
        instrument_nodes = await self.get_instrument_nodes()
        self.instrument_nodes = instrument_nodes
        # print("Engine stuff", " PID: ", self.PID)
        for port in all_ports:
            # with nodes we can associate nodes with clients/instruments via PID
            # And ports with nodes via ID/node.id
            # With those IDs in place we can start calling pw-link

            # TODO: there is a bug in this function where it will give all of the ports to all instruments

            for instrument_node in instrument_nodes:
                # print(instrument_node.get("id", None), port.get("info",{}).get("props", {}).get("node.id", None))
                if port.get("info", {}).get("props", {}).get(
                    "node.id", None
                ) == instrument_node.get("id", None):
                    # print("ID correct", instrument_node.get("id", None))
                    if port.get("info", {}).get("direction", None):
                        if "output" in port.get("info", []).get("props", []).get(
                            "port.name", "None"
                        ):
                            self.pw_ports["output"].append(port)
                        elif "input" in port.get("info", []).get("props", []).get(
                            "port.name", "None"
                        ):
                            self.pw_ports["input"].append(port)

        # for port in self.pw_ports["input"]:
        #     print(port["id"])
        # print("in ports: ", len(self.pw_ports["input"]))
        # print("out ports: ", len(self.pw_ports["output"]))
        await self.get_instrument_duplex_node()
        await self.get_instrument_duplex_ports()
        # print(self.duplex_ports)

    async def updateConfig(self):
        self.PID = self.process.pid
        pwConfig = await getPipewireConfigForPID(self.PID)
        if pwConfig:
            self.pipewire = pwConfig
            self.pipewireID = pwConfig["id"]


async def setVolumeByPipewireID(pipewire_id, volume):
    proc = await asyncio.create_subprocess_shell(
        ["pw-cli", "s", pipewire_id, f"Props '{{mute: false, volume:{volume}}}'"],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if stdout:
        print(stdout.decode().strip())
    elif stderr:
        print(stderr.decode().strip())


async def connectPipewireSourceToPipewireDest(source_id, dest_id):
    if not source_id or not dest_id:
        raise Exception("Invalid call to connectPipewireSourcetoPipewireDest()")

    try:
        cmd = f"pw-link {str(source_id)} {str(dest_id)}"
        # print(cmd)
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
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
        raise Exception("Invalid call to disconnectPipewireSourceFromPipewireDest()")
    try:
        cmd = f"pw-link -d {str(source_id)} {str(dest_id)}"
        # print(cmd)
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except Exception as e:
        print("Error in disconnectPipewireSourceToPipewireDest")
        print(e)
    stdout, stderr = await proc.communicate()

    if stdout:
        print(stdout.decode().strip())
    elif stderr:
        print(stderr.decode().strip())


# Given an engine PID, run pw-dump until the PID shows up and then return that node config
async def getPipewireConfigForPID(pid):
    if not pid:
        raise Exception("No PID provided to getPipewireConfigForPID()")
    i = 0
    while True:
        try:
            proc = await asyncio.create_subprocess_shell(
                "pw-dump -N Node",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                data = json.loads(stdout.decode().strip())
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

    proc = await asyncio.create_subprocess_shell(
        "pw-dump -N Client",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if stdout:
        data = json.loads(stdout.decode().strip())
        return data


async def getAllNodes():
    proc = await asyncio.create_subprocess_shell(
        "pw-dump -N Node",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    data = []
    if stderr:
        print("getAllNodes ERROR:")
        print(stderr)
    if stdout:
        try:
            data = json.loads(stdout.decode().strip())
        except Exception as e:
            print(e)
            # print(stdout)
    return data


async def getAllPorts():
    proc = await asyncio.create_subprocess_shell(
        "pw-dump -N Port",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if stderr:
        print(stderr.decode())

    if stdout:
        data = json.loads(stdout.decode().strip())
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
