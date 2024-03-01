import json
import asyncio
from glob import glob
from pathlib import Path
from osc_device import OSCDevice
import definitions
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_server import AsyncIOOSCUDPServer
from pythonosc.dispatcher import Dispatcher
from unittest.mock import MagicMock

client = SimpleUDPClient("127.0.0.1", 88888)
dispatcher = Dispatcher()
loop = asyncio.get_event_loop()
server = AsyncIOOSCUDPServer(("127.0.0.1", 99999), dispatcher, loop)

client.send_message = MagicMock(name='send_message')
dispatcher.map = MagicMock(name='map')

test_cases = ["twist_1","filtera","classic_1"]

device_definitions =  [json.load(open(device_file)) for device_file in [f"{definitions.DEVICE_DEFINITION_FOLDER}/{name}.json" for name in test_cases]]

menus, nested_menus, no_menu = device_definitions

osc = {'client': client, 'server': server, 'dispatcher': dispatcher}

def test_menus():
    device = OSCDevice('menus', menus, osc)

    assert len(device.controls) == 12, "Twist should have 12 controls (including spacers)"
    
    