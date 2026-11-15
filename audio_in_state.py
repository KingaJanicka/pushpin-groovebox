"""A Surge slot's Audio In routing, kept in a sidecar file next to its patch.

Surge's ``.fxp`` holds its own parameters (an oscillator being Audio In, its
gain and filters) but not what pushpin links into the track's duplex (Pd
passthrough) node: which source feeds each of its 8 stereo columns, and each
column's level. Those are saved here, beside the slot's state patch, as
``<surge_state>/<track>_<slot>.audio_in.json``::

    {"columns": [{"source": "Pushpin 2", "port": null}, null, ...],
     "gains": [0.8, 0.0, ...]}

A source is saved by name (a track's name, or "Overwitch" plus the name of its
output), never by PipeWire port id: ids are new whenever a node restarts.
"""

import json
import logging
import os

from engine import connectPipewireSourceToPipewireDest
from engine import disconnectPipewireSourceFromPipewireDest

log = logging.getLogger("audio_in_state")

COLUMNS = 8
SUFFIX = ".audio_in.json"


def sidecar_path(folder, track, slot):
    return os.path.join(folder, f"{track}_{slot}{SUFFIX}")


def snapshot(eng):
    """The engine's routing and gains, or None when nothing is routed and every
    gain is 0 (there's nothing to keep)."""
    columns = []
    for connection in eng.connections:
        source = connection.get("source")
        if source is None or connection.get("L") is None:
            columns.append(None)
        else:
            columns.append({"source": source, "port": connection.get("port")})
    gains = [float(g or 0.0) for g in eng.audio_in_gains]
    if all(c is None for c in columns) and not any(gains):
        return None
    return {"columns": columns, "gains": gains}


def save(path, eng):
    """Write the engine's routing to ``path``; with nothing to keep, remove a
    stale sidecar instead (the slot's patch is saved without Audio In routing)."""
    data = snapshot(eng)
    try:
        if data is None:
            if os.path.isfile(path):
                os.remove(path)
            return
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=1)
    except OSError as e:
        log.warning("could not save %s: %s", path, e)


def load(path):
    """The sidecar's data, or None if there's none (or it can't be read)."""
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        log.warning("could not read %s: %s", path, e)
        return None
    columns = list(data.get("columns") or [])[:COLUMNS]
    columns += [None] * (COLUMNS - len(columns))
    gains = [float(g or 0.0) for g in list(data.get("gains") or [])[:COLUMNS]]
    gains += [0.0] * (COLUMNS - len(gains))
    return {"columns": columns, "gains": gains}


def available_sources(app):
    """What can feed a column: every track, and Overwitch once it's running."""
    sources = list(app.instruments.values())
    external = app.external_instruments[0] if app.external_instruments else None
    if external is not None and external.engine.PID is not None:
        sources.append(external)
    return sources


def source_ports(app, source, port_label=None):
    """(L, R) PipeWire port ids ``source`` feeds a column with, or None.
    Overwitch feeds both sides from its output called ``port_label``."""
    if source is None:
        return None
    if source in app.external_instruments:
        for port in source.engine.pw_ports["output"]:
            if port_label is not None and port["info"]["props"].get("port.name") == port_label:
                return port["id"], port["id"]
        return None
    eng = source.engine
    out_L_name, out_R_name = eng.output_port_names
    source_L = next((p["id"] for p in eng.pw_ports["output"] if eng.port_is(p, (out_L_name,))), None)
    source_R = next((p["id"] for p in eng.pw_ports["output"] if eng.port_is(p, (out_R_name,))), None)
    if source_L is None or source_R is None:
        return None
    return source_L, source_R


def restore(app, eng, data):
    """Make the engine's duplex node route and level its columns as ``data``
    says (None: nothing routed). Links go on ``app.queue``, like the Audio In
    device's. A saved source that isn't there now leaves its column empty.
    Does nothing while the duplex node isn't up: starting it restores then."""
    if not all(
        eng.duplex_ports["inputs"][f"Input {c}"]["L"] and eng.duplex_ports["inputs"][f"Input {c}"]["R"]
        for c in range(COLUMNS)
    ):
        return
    columns = data["columns"] if data else [None] * COLUMNS
    sources = {s.name: s for s in available_sources(app)}

    for column, wanted in enumerate(columns):
        duplex_in = eng.duplex_ports["inputs"][f"Input {column}"]
        duplex_in_L, duplex_in_R = duplex_in["L"]["id"], duplex_in["R"]["id"]
        new_L = new_R = None
        source_label = port_label = None
        if wanted:
            source = sources.get(wanted.get("source"))
            port_label = wanted.get("port")
            ports = source_ports(app, source, port_label)
            if ports is None:
                log.warning("Audio In: saved source %r for column %s isn't available",
                            wanted.get("source"), column)
                port_label = None
            else:
                new_L, new_R = ports
                source_label = source.name

        connection = eng.connections[column]
        old_L, old_R = connection.get("L"), connection.get("R")
        if (old_L, old_R) != (new_L, new_R):
            if old_L is not None and old_R is not None:
                app.queue.append(disconnectPipewireSourceFromPipewireDest(old_L, duplex_in_L))
                app.queue.append(disconnectPipewireSourceFromPipewireDest(old_R, duplex_in_R))
            if new_L is not None and new_R is not None:
                app.queue.append(connectPipewireSourceToPipewireDest(new_L, duplex_in_L))
                app.queue.append(connectPipewireSourceToPipewireDest(new_R, duplex_in_R))
        connection["L"], connection["R"] = new_L, new_R
        connection["source"] = source_label
        connection["port"] = port_label

    eng.audio_in_gains[:] = data["gains"] if data else [0.0] * COLUMNS
    send_gains(eng)


def send_gains(eng):
    """Send every column's level to the duplex node (both sides of each column)."""
    client = getattr(eng, "duplex_node_osc_client", None)
    if client is None:
        return
    for column, gain in enumerate(eng.audio_in_gains):
        value = float(gain or 0.0)
        client.send_message(f"/vol_{2 * column}", value)
        client.send_message(f"/vol_{2 * column + 1}", value)
