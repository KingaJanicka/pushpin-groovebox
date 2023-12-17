import asyncio
from pythonosc.dispatcher import Dispatcher
from pythonosc.udp_client import SimpleUDPClient
from typing import List, Any
import time

# def play_note(client):
#     while True:
#         print("sending notes")
#         client.send_message("/mnote", [68.0, 120.0])
#         time.sleep(1)
#         client.send_message("/mnote/rel", [68.0, 120.0])
#         time.sleep(1)

async def log_stdout(proc, label):
    print(label, "LABEL")
    print(proc, "proc")
    
    line = await proc.stdout.readline()
    
    while line:
        print(f'{label} {line.decode()}')
        line = await proc.stdout.readline()

    
OSC_PORT_IN_MIN = 1030
OSC_PORT_IN_MAX = 1038
OSC_PORT_OUT_MIN = 1040
OSC_PORT_OUT_MAX = 1048

async def run(cmd, label):
    proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE)
    try:
        await asyncio.gather(log_stdout(proc, label))
    finally:
        proc.terminate()
        
async def init_surge():
    await asyncio.gather(
        run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1030 --osc-out-port=1040', "s1"),
        run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1031 --osc-out-port=1041', "s2"),
        run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1032 --osc-out-port=1042', "s3"),
        run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1033 --osc-out-port=1043', "s4"),
        run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1034 --osc-out-port=1044', "s5"),
        run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1035 --osc-out-port=1045', "s6"),
        run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1036 --osc-out-port=1046', "s7"),
        run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1037 --osc-out-port=1047', "s8"),
        run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1038 --osc-out-port=1048', "s9")),

    
    
   
   

# asyncio.run(init_surge())