import asyncio
import json

async def getAllClients():
    proc = await asyncio.create_subprocess_shell(
        "pw-dump -N Client",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    data = []
    if stderr:
        print("getAllClients ERROR:")
        print(stderr)
    if stdout:
        try:
            data = json.loads(stdout.decode().strip())
        except Exception as e:
            print(e)
            print(stdout.decode().strip())
            #calling again because we got trash json
            print("recursive getAllClients")
            await getAllClients()
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




def getAllConnectionsToNode(self):
    # this will use     pw-link -l id   command
    # where ID is the pipewire id of the instance you want to know connections of
    # this will list both inputs and outputs
    pass


### Connect using pw-cli create-link <pipewire-id> <port-id> <pipewire-id> <port-id>

### Conenct using PW-Link pw-link <port "id"> <port "id">
### get port IDs with pw-dump Port
### ensure which surge instance is which with object.id

