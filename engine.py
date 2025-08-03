from abc import ABC
import asyncio
import traceback
import sys
import json
import logging
from signal import SIGINT
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher

logger = logging.getLogger("engine.py")
# logging.basicConfig(level=logging.DEBUG)
# logging.getLogger().setLevel(level=logging.DEBUG)

class Engine(ABC):
    app = None
    type = None
    PID = None
    PD_PID = None
    pipewireID = None
    pipewire = None
    process = None
    pd_process = None
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
        app,
        sample_rate=44100,
        buffer_size=64,
        midi_device_idx=None,
        instrument_definition=None,
    ):
        self.app = app
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
        # TODO: We should prob init all the isobar timeline and midi in/out right here
        # This should be after midi
        # self.connections.append(await self.createLoopback())
        
        pass

  
        


    async def configure_pipewire(self):

        instrument_nodes = await self.get_instrument_nodes()
        self.instrument_nodes = instrument_nodes
        all_ports = filter(
            lambda x: x["type"] == "PipeWire:Interface:Port", self.app.pipewire
        )
        for port in all_ports:
            # with nodes we can associate nodes with clients/instruments via PID
            # And ports with nodes via ID/node.id
            # With those IDs in place we can start calling pw-link

            for instrument_node in instrument_nodes:
                if port.get("info", {}).get("props", {}).get(
                    "node.id", None
                ) == instrument_node.get("id", None):
                    if port.get("info", {}).get("direction", None):
                        # TODO: this needs to be re-written to be handled a bit better with the PW rewrite
                        # So we don't have sperate cases for surge and OW
                        # Need to make sure monitor outs won't end up in "outputs"
                        
                        if self.instrument["instrument_name"] == "Overwitch":
                            if (
                                port.get("info", [])
                                .get("props", [])
                                .get("port.direction", "None")
                                == "out"
                                and port.get("info", [])
                                .get("props", [])
                                .get("format.dsp", "None")
                                != "8 bit raw midi"
                            ):
                                self.pw_ports["output"].append(port)
                            elif (
                                port.get("info", [])
                                .get("props", [])
                                .get("port.direction", "None")
                                == "in"
                                and port.get("info", [])
                                .get("props", [])
                                .get("format.dsp", "None")
                                != "8 bit raw midi"
                            ):
                                self.pw_ports["input"].append(port)

                        elif "output" in port.get("info", []).get("props", []).get(
                            "port.name", "None"
                        ):
                            self.pw_ports["output"].append(port)

                        elif "input" in port.get("info", []).get("props", []).get(
                            "port.name", "None"
                        ):
                            self.pw_ports["input"].append(port)


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
        clients = filter(
            lambda x: x["type"] == "PipeWire:Interface:Client", self.app.pipewire.copy()
        )
        nodes = filter(
            lambda x: x["type"] == "PipeWire:Interface:Node", self.app.pipewire.copy()
        )
        client_id = [None]
        try:
            for client in clients:
                if client and client.get("info", {}).get("props", {}).get(
                    "application.process.id", None
                ) == (self.PID):
                    client_id.append(client["id"])
                    # print("client ID", client_id)

            instrument_nodes = []
            for node in nodes:
                for id in client_id:
                    if (
                        node
                        and id != None
                        and node.get("info", {}).get("props", {}).get("client.id", None)
                        == (id)
                    ):
                        instrument_nodes.append(node)
            return instrument_nodes
        except Exception as e:
            print("Exception in get_instrument_nodes in engine.py")
            traceback.print_exc()

    async def get_instrument_duplex_node(self):
        nodes = filter(
            lambda x: x["type"] == "PipeWire:Interface:Node", self.app.pipewire
        )

        # Gets the right node, so we can adjust volumes and get the ID for ports
        for node in nodes:
            if (
                node.get("info", []).get("props", []).get("application.process.id", None)
                == self.PD_PID
            ):
                self.duplex_node = node
                return node

    async def get_instrument_duplex_ports(self):
        print("get duplex ports called")
        ports = filter(
            lambda x: x["type"] == "PipeWire:Interface:Port", self.app.pipewire
        )
        unsorted_duplex_ports = []

        if not self.duplex_node:
            await self.get_instrument_duplex_node()

        for port in ports:
            # print(port["info"]["props"]["node.id"],  self.duplex_node["id"])
            if (
                self.duplex_node
                and port["info"]["props"]["node.id"] == self.duplex_node["id"]
            ):
                unsorted_duplex_ports.append(port)
        print("unsorted ports")
        for port in unsorted_duplex_ports:
            
            # TODO: Aendra really hates this perfectly reasonable match statement
            # port_name = port["info"]["props"]["port.name"]

            # port_type, port_index = port_name.split('_')

            # if port_type not in ['playback', 'capture']:
            #     continue

            # channel = "R" if int(port_index) % 2 else "L"
            # input_index = int(port_index) - 1 if channel == 'L' else int(port_index) - 2
            # self.duplex_ports["inputs" if port_type == 'playback' else 'outputs'][f"{'Input' if port_type == 'playback' else 'Output'} {input_index}"][channel] = port
           
            
            match port["info"]["props"]["port.name"]:
                case "pure_data:input_1":
                    self.duplex_ports["inputs"]["Input 0"]["L"] = port
                case "pure_data:input_2":
                    self.duplex_ports["inputs"]["Input 0"]["R"] = port
                case "pure_data:input_3":
                    self.duplex_ports["inputs"]["Input 1"]["L"] = port
                case "pure_data:input_4":
                    self.duplex_ports["inputs"]["Input 1"]["R"] = port
                case "pure_data:input_5":
                    self.duplex_ports["inputs"]["Input 2"]["L"] = port
                case "pure_data:input_6":
                    self.duplex_ports["inputs"]["Input 2"]["R"] = port
                case "pure_data:input_7":
                    self.duplex_ports["inputs"]["Input 3"]["L"] = port
                case "pure_data:input_8":
                    self.duplex_ports["inputs"]["Input 3"]["R"] = port
                case "pure_data:input_9":
                    self.duplex_ports["inputs"]["Input 4"]["L"] = port
                case "pure_data:input_10":
                    self.duplex_ports["inputs"]["Input 4"]["R"] = port
                case "pure_data:input_11":
                    self.duplex_ports["inputs"]["Input 5"]["L"] = port
                case "pure_data:input_12":
                    self.duplex_ports["inputs"]["Input 5"]["R"] = port
                case "pure_data:input_13":
                    self.duplex_ports["inputs"]["Input 6"]["L"] = port
                case "pure_data:input_14":
                    self.duplex_ports["inputs"]["Input 6"]["R"] = port
                case "pure_data:input_15":
                    self.duplex_ports["inputs"]["Input 7"]["L"] = port
                case "pure_data:input_16":
                    self.duplex_ports["inputs"]["Input 7"]["R"] = port
                case "pure_data:output_1":
                    self.duplex_ports["outputs"]["Output 0"]["L"] = port
                case "pure_data:output_2":
                    self.duplex_ports["outputs"]["Output 0"]["R"] = port
                case "pure_data:output_3":
                    self.duplex_ports["outputs"]["Output 1"]["L"] = port
                case "pure_data:output_4":
                    self.duplex_ports["outputs"]["Output 1"]["R"] = port
                case "pure_data:output_5":
                    self.duplex_ports["outputs"]["Output 2"]["L"] = port
                case "pure_data:output_6":
                    self.duplex_ports["outputs"]["Output 2"]["R"] = port
                case "pure_data:output_7":
                    self.duplex_ports["outputs"]["Output 3"]["L"] = port
                case "pure_data:output_8":
                    self.duplex_ports["outputs"]["Output 3"]["R"] = port
                case "pure_data:output_9":
                    self.duplex_ports["outputs"]["Output 4"]["L"] = port
                case "pure_data:output_10":
                    self.duplex_ports["outputs"]["Output 4"]["R"] = port
                case "pure_data:output_11":
                    self.duplex_ports["outputs"]["Output 5"]["L"] = port
                case "pure_data:output_12":
                    self.duplex_ports["outputs"]["Output 5"]["R"] = port
                case "pure_data:output_13":
                    self.duplex_ports["outputs"]["Output 6"]["L"] = port
                case "pure_data:output_14":
                    self.duplex_ports["outputs"]["Output 6"]["R"] = port
                case "pure_data:output_15":
                    self.duplex_ports["outputs"]["Output 7"]["L"] = port
                case "pure_data:output_16":
                    self.duplex_ports["outputs"]["Output 7"]["R"] = port
                case _:
                    pass


class SurgeXTEngine(Engine):
        
    puredata_process_id = None
    puredata_client_id = None
    # Magic number is defined in the puradata patch
    duplex_node_osc_address = None
    duplex_node_osc_client = None
    duplex_node_osc_server = None
    duplex_node_osc = None
    duplex_client = None
    duplex_node = None
    log_in = None
    instrument_index = None
    def __init__(
        self,
        app,
        sample_rate=44100,
        buffer_size=64,
        midi_device_idx=None,
        instrument_definition=None,
        
    ):
        super().__init__(
            app=app,
            sample_rate=sample_rate,
            buffer_size=buffer_size,
            midi_device_idx=midi_device_idx,
            instrument_definition=instrument_definition,
        )
        self.duplex_node_osc_address = self.instrument["duplex_osc_port"]
        self.instrument_index = self.instrument["instrument_index"]
        # Setup stuff for the volume node osc client
        dispatcher = Dispatcher()
        self.log_in = logger.getChild(f"in-{self.duplex_node_osc_address}")
        dispatcher.set_default_handler(lambda *message: self.log_in.debug(message))
        self.duplex_node_osc_client = SimpleUDPClient("127.0.0.1", int(self.duplex_node_osc_address))
        self.duplex_node_osc = {"client": self.duplex_node_osc_client, "server": self.duplex_node_osc_server, "dispatcher": dispatcher}
        
    async def configure_pipewire(self):
        await super().configure_pipewire()
        # d/c from default sinks
        # get instrument links
        # print([instrument['info']['props']['media.class'] for instrument in self.instrument_nodes if instrument['info']['props']['media.class']])

        surge_output_node = [instrument for instrument in self.instrument_nodes if instrument['info']['props']['media.class'] == 'Stream/Output/Audio'].pop()

        surge_output_ports = [port for port in self.app.pipewire if port['type'] == 'PipeWire:Interface:Port' and port['info']['props']['node.id'] == surge_output_node['id']]
        init_links = [link for link in self.app.pipewire if link['type'] == 'PipeWire:Interface:Link' and link['info']['output-node-id'] == surge_output_node['id']]

        for link in init_links:
            await disconnectPipewireLink(link['id'])
            
        # connect source of link to duplex in
        volume_node = self.app.get_volume_node()
        if not volume_node:
            raise Exception('Volume Duplex node not found')
        
        volume_ports = [port for port in self.app.pipewire if port['type'] == 'PipeWire:Interface:Port' and port['info']['props']['node.id'] == volume_node['id']]
        
        midi_channel = self.instrument['midi_channel']
        volume_input_port_index_L = midi_channel * 2
        volume_input_port_index_R = (midi_channel * 2) + 1


        # Those lines here decide what's connecting to what
        volume_L_input = [port for port in volume_ports if port['info']['props']['object.path'] == f"pure_data:input_{volume_input_port_index_L}"].pop()
        volume_R_input = [port for port in volume_ports if port['info']['props']['object.path'] == f"pure_data:input_{volume_input_port_index_R}"].pop()

        surge_L = [port for port in surge_output_ports if port['info']['props']['port.name'] == 'output_FL'].pop()
        surge_R = [port for port in surge_output_ports if port['info']['props']['port.name'] == 'output_FR'].pop()


        await connectPipewireSourceToPipewireDest(surge_L['id'], volume_L_input['id'])
        await connectPipewireSourceToPipewireDest(surge_R['id'], volume_R_input['id'])

        # connect duplex out to destination of link
        volume_L_output = [port for port in volume_ports if port['info']['props']['object.path'] == f"pure_data:output_{volume_input_port_index_L}"].pop()
        volume_R_output = [port for port in volume_ports if port['info']['props']['object.path'] == f"pure_data:output_{volume_input_port_index_R}"].pop()

        interface_L_port = [link['info']['input-port-id'] for link in init_links if link['info']['output-port-id'] == surge_L['id']].pop()
        interface_R_port = [link['info']['input-port-id'] for link in init_links if link['info']['output-port-id'] == surge_R['id']].pop()

        await connectPipewireSourceToPipewireDest(volume_L_output['id'], interface_L_port)
        await connectPipewireSourceToPipewireDest(volume_R_output['id'], interface_R_port)

    async def start_pd_node(self):
        # await asyncio.sleep(1)
        self.pd_process = await asyncio.create_subprocess_exec(
            "pw-jack",
            "puredata",
            "-jack",
            "-nogui",
            "-rt",
            "-audiobuf",
            "25",
            # "-blocksize"
            # "1024",
            # "-r"
            # "48000",
            f"./puredata_nodes/passthrough_{self.instrument_index}.pd",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.PIPE,
            
        )
        self.puredata_process_id = self.pd_process.pid

        await self.app.get_pipewire_config()
        self.get_duplex_client()
        self.get_duplex_node()
        await self.get_duplex_ports()
        await self.disconnect_links_from_duplex_node()
        
    
    
    async def kill_pd_node(self):
        self.pd_process.kill()
        self.puredata_process_id = None
    
    def get_duplex_client(self):
        for item in self.app.pipewire:
            if item["type"] == "PipeWire:Interface:Client":
                # print(item.get("info", {}).get("props", {}).get("application.process.id",None), self.puredata_process_id)
                try:
                    id = item.get("info", {}).get("props", {}).get("application.process.id",None)
                    if id == self.puredata_process_id:
                        self.duplex_client = item
                        self.puredata_client_id = self.duplex_client.get("id", None)
                except:
                    pass
        
        return self.duplex_client


    def get_duplex_node(self):
        for node in self.app.pipewire:
            if node["type"] == "PipeWire:Interface:Node":
                try:
                    id = node.get("info", {}).get("props", {}).get("client.id",None)
                    if id == self.puredata_client_id:
                        self.duplex_node = node
                except:
                    pass
        return self.duplex_node
        
        
    async def disconnect_links_from_duplex_node(self):
        # init_links = [link for link in self.pipewire if link['type'] == 'PipeWire:Interface:Link' and link['info']['output-node-id'] == self.volume_node['id']]
        link_list = []
        for link in self.app.pipewire: 
            if link['type'] == 'PipeWire:Interface:Link':
                # print(link['info']['output-node-id'], "  ", link['info']['input-node-id'], "  ", self.volume_node['id'], )
                if link['info']['output-node-id'] == self.duplex_node['id'] or link['info']['input-node-id'] == self.duplex_node['id']:
                    link_list.append(link)
        for link in link_list:
            await disconnectPipewireLink(link['id'])
    

    async def get_duplex_ports(self):
        ports = filter(
            lambda x: x["type"] == "PipeWire:Interface:Port", self.app.pipewire
        )
        unsorted_duplex_ports = []

        if not self.duplex_node:
            self.get_duplex_node()
            
        for port in ports:
            # print(port["info"]["props"]["node.id"],  self.duplex_node["id"])
            if (
                self.duplex_node
                and port["info"]["props"]["node.id"] == self.duplex_node["id"]
            ):
                unsorted_duplex_ports.append(port)
        # print(len(unsorted_duplex_ports))
        for port in unsorted_duplex_ports:
            
            # TODO: Aendra really hates this perfectly reasonable match statement
            # port_name = port["info"]["props"]["port.name"]

            # port_type, port_index = port_name.split('_')

            # if port_type not in ['playback', 'capture']:
            #     continue

            # channel = "R" if int(port_index) % 2 else "L"
            # input_index = int(port_index) - 1 if channel == 'L' else int(port_index) - 2
            # self.duplex_ports["inputs" if port_type == 'playback' else 'outputs'][f"{'Input' if port_type == 'playback' else 'Output'} {input_index}"][channel] = port
           
            # print(port["info"]["props"]["port.name"]) 
            match port["info"]["props"]["port.name"]:
                case "input_1":
                    self.duplex_ports["inputs"]["Input 0"]["L"] = port
                case "input_2":
                    self.duplex_ports["inputs"]["Input 0"]["R"] = port
                case "input_3":
                    self.duplex_ports["inputs"]["Input 1"]["L"] = port
                case "input_4":
                    self.duplex_ports["inputs"]["Input 1"]["R"] = port
                case "input_5":
                    self.duplex_ports["inputs"]["Input 2"]["L"] = port
                case "input_6":
                    self.duplex_ports["inputs"]["Input 2"]["R"] = port
                case "input_7":
                    self.duplex_ports["inputs"]["Input 3"]["L"] = port
                case "input_8":
                    self.duplex_ports["inputs"]["Input 3"]["R"] = port
                case "input_9":
                    self.duplex_ports["inputs"]["Input 4"]["L"] = port
                case "input_10":
                    self.duplex_ports["inputs"]["Input 4"]["R"] = port
                case "input_11":
                    self.duplex_ports["inputs"]["Input 5"]["L"] = port
                case "input_12":
                    self.duplex_ports["inputs"]["Input 5"]["R"] = port
                case "input_13":
                    self.duplex_ports["inputs"]["Input 6"]["L"] = port
                case "input_14":
                    self.duplex_ports["inputs"]["Input 6"]["R"] = port
                case "input_15":
                    self.duplex_ports["inputs"]["Input 7"]["L"] = port
                case "input_16":
                    self.duplex_ports["inputs"]["Input 7"]["R"] = port
                case "output_1":
                    self.duplex_ports["outputs"]["Output 0"]["L"] = port
                case "output_2":
                    self.duplex_ports["outputs"]["Output 0"]["R"] = port
                case "output_3":
                    self.duplex_ports["outputs"]["Output 1"]["L"] = port
                case "output_4":
                    self.duplex_ports["outputs"]["Output 1"]["R"] = port
                case "output_5":
                    self.duplex_ports["outputs"]["Output 2"]["L"] = port
                case "output_6":
                    self.duplex_ports["outputs"]["Output 2"]["R"] = port
                case "output_7":
                    self.duplex_ports["outputs"]["Output 3"]["L"] = port
                case "output_8":
                    self.duplex_ports["outputs"]["Output 3"]["R"] = port
                case "output_9":
                    self.duplex_ports["outputs"]["Output 4"]["L"] = port
                case "output_10":
                    self.duplex_ports["outputs"]["Output 4"]["R"] = port
                case "output_11":
                    self.duplex_ports["outputs"]["Output 5"]["L"] = port
                case "output_12":
                    self.duplex_ports["outputs"]["Output 5"]["R"] = port
                case "output_13":
                    self.duplex_ports["outputs"]["Output 6"]["L"] = port
                case "output_14":
                    self.duplex_ports["outputs"]["Output 6"]["R"] = port
                case "output_15":
                    self.duplex_ports["outputs"]["Output 7"]["L"] = port
                case "output_16":
                    self.duplex_ports["outputs"]["Output 7"]["R"] = port
                case _:
                    pass

        # print(self.duplex_ports)

    def getPID(self):
        return self.PID

    def getInstrumentPipewireID(self):
        return self.pipewire["id"]

    def getObjectSerial(self):
        return self.pipewire["info"]["props"]["object.serial"]

    async def start(self):
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

    async def updateConfigPureData(self,):

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
        # print("source id:", source_id, "dest_id", dest_id)
        cmd = f"pw-link {str(source_id)} {str(dest_id)}"
        # print(cmd)
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except Exception as e:
        print("Error in connectPipewireSourceToPipewireDest")
        traceback.print_exc()
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
        traceback.print_exc()
    stdout, stderr = await proc.communicate()

    if stdout:
        print(stdout.decode().strip())
    elif stderr:
        print(stderr.decode().strip())


async def disconnectPipewireLink(link_id):
    if not link_id:
        raise Exception("Invalid call to disconnectPipewireSourceFromPipewireDest()")
    try:
        cmd = f"pw-link -d {str(link_id)}"
        # print(cmd)
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except Exception as e:
        print("Error in disconnectPipewireSourceToPipewireDest")
        traceback.print_exc()
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


class ExternalEngine(Engine):
    def __init__(
        self,
        app,
        sample_rate=44100,
        buffer_size=128,
        midi_device_idx=None,
        instrument_definition={},  
        # TODO: create stub instrument def
    ):
        super().__init__(
            app,
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

        await asyncio.sleep(1)
        self.process = await asyncio.create_subprocess_exec(
            "pw-jack",
            "overwitch-cli",
            "-n",
            "0",
            f"-b",
            f"8",
            f"-q",
            f"4",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            # stderr=asyncio.subprocess.PIPE,
            
        )
        
        self.PID = self.process.pid

        await asyncio.sleep(2)

    async def updateConfig(self):
        self.PID = self.process.pid
        pwConfig = await getPipewireConfigForPID(self.PID)
        if pwConfig:
            self.pipewire = pwConfig
            self.pipewireID = pwConfig["id"]
