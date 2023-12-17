import asyncio
from pythonosc.dispatcher import Dispatcher
from pythonosc.udp_client import SimpleUDPClient
from typing import List, Any
import time

def play_note(client):
    while True:
        print("sending notes")
        client.send_message("/mnote", [68.0, 120.0])
        time.sleep(1)
        client.send_message("/mnote/rel", [68.0, 120.0])
        time.sleep(1)

async def log_stdout(proc, label):
    print(label, "LABEL")
    print(proc, "proc")
    
    line = await proc.stdout.readline()
    
    while line:
        print(f'{label} {line.decode()}')
        line = await proc.stdout.readline()

    


async def run(cmd, label):
    proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE)
    client = SimpleUDPClient("127.0.0.1", 1032)
    try:
        await asyncio.gather(log_stdout(proc, label), play_note(client))
    finally:
        proc.terminate()
        
async def main():
    await asyncio.gather(
        # run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1031 --osc-out-port=1041', "s1"),
        run('/usr/bin/surge-xt-cli --sample-rate=48000 --osc-in-port=1032 --osc-out-port=1042', "s2"))
    
    
   
   

# asyncio.run(main())
client = SimpleUDPClient("127.0.0.1", 1032)
play_note(client)