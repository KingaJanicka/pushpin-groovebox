"""Loading device-page definitions (the JSON files under definitions/ and
engines/*/definitions/)."""
from __future__ import annotations

import json
import os
from glob import glob
from pathlib import Path


def load_device_definitions(folder: str) -> dict[str, dict]:
    """Every ``*.json`` in ``folder`` keyed by file stem, in file-name order (which is page order)."""
    definitions: dict[str, dict] = {}
    for path in sorted(glob(os.path.join(folder, "*.json"))):
        with open(path) as f:
            definitions[Path(path).stem] = json.load(f)
    return definitions
