import json
from pathlib import Path
from glob import glob
import os

with open("./effect_definitions/bla/test.json", "r+") as infile:
    my_data = json.load(infile)

device_names = [
    Path(device_file).stem for device_file in glob("./effect_definitions/bla/*.json")
]

for device_name in device_names:
    print("device name", device_name)
    try:
        with open(
            "./effect_definitions/bla/{}.json".format(device_name), "r+"
        ) as infile:
            my_data = json.load(infile)
            my_data["slot"] = int(5)

        with open(
            "./effect_definitions/bla/{}.json".format(device_name), "w"
        ) as outfile:
            json.dump(my_data, outfile)
    except FileNotFoundError:
        print("error")
