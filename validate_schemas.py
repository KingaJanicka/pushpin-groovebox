from jsonschema import validate
import definitions
import json
import os
from glob import glob
from pathlib import Path


device_schema = json.load(open(os.path.join("./docs/schemas/v2/device.json")))

device_names = [
    Path(device_file).stem for device_file in glob("./device_definitions/*.json")
]
device_definitions = {}

for device_name in device_names:
    try:
        device_definitions[device_name] = json.load(
            open(
                os.path.join(
                    definitions.DEVICE_DEFINITION_FOLDER,
                    "{}.json".format(device_name),
                )
            )
        )
    except FileNotFoundError:
        device_definitions[device_name] = {}

for device_name in device_definitions:
    device = device_definitions[device_name]
    validate(instance=device, schema=device_schema)
