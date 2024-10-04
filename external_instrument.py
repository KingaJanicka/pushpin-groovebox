import logging
import engine
import mido
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
from osc_device import OSCDevice
from mod_matrix_device import ModMatrixDevice
from audio_in_device import AudioInDevice
from definitions import PyshaMode
import asyncio
logger = logging.getLogger("osc_instrument")
# logger.setLevel(level=logging.DEBUG)


class ExternalInstrument(PyshaMode):
    engine = None
    
    def __init__(
        self,
        app,
        instrument_short_name,
        instrument_definition,
        **kwargs
    ):
        self.transports = []
        self.devices = []
        self.instrument_nodes = []
        self.instrument_ports = []
        self.name = instrument_short_name
        self.midi_port = mido.open_output(
            instrument_definition["instrument_short_name"],
            client_name=instrument_definition["instrument_short_name"],
        )
        midi_device_idx = [els.split(":")[0] for els in mido.get_input_names()].index(
            instrument_definition["instrument_short_name"]
        )
      
        self.engine = engine.ExternalEngine(app, midi_device_idx=midi_device_idx, instrument_definition=instrument_definition)

    """
    Initialise OSC servers and add to transport array so they can be gracefully closed
    """

    async def start(self, loop):
        asyncio.create_task(self.engine.start())