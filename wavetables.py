"""Surge XT wavetable ids, by name.

Surge picks a wavetable over OSC by id only (``/wavetable/a/osc/1/id <n>``),
and an id is the wavetable's position in the list Surge builds at startup by
reading its ``wavetables`` folder. That list is in the order the filesystem
returns directory entries, not alphabetical: the same wavetable has a
different id on a Mac (APFS) than on the Pi (ext4), and can change when Surge
is reinstalled. So a device definition names a wavetable ("Basic/Sine") and
the id is worked out here, by reading the same folder the same way Surge does
(``os.scandir`` and Surge's ``std::filesystem`` iterators both return raw
``readdir`` order).

Only the factory folder is read. Surge reads it first, so factory ids don't
depend on third-party or user wavetables; those come after it.
"""
from __future__ import annotations

import functools
import logging
import os

import definitions

logger = logging.getLogger("wavetables")

WAVETABLE_EXTENSIONS = (".wt", ".wav")

# Where Surge keeps its factory data: the Pi's, then a Mac install's (for
# development; Surge's own lookup on macOS)
FACTORY_FOLDERS = (
    os.path.join(definitions.SURGE_XT_ROOT, "wavetables"),
    "/Library/Application Support/Surge XT/wavetables",
)


def scan_wavetables(folder: str) -> list[str]:
    """Every wavetable under ``folder`` as "Category/Name", in Surge's id order:
    each folder (recursively, depth first, in directory order) and then the
    files directly in it, in directory order."""
    folders = [folder]

    def add_subfolders(path: str) -> None:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir():
                    folders.append(entry.path)
                    add_subfolders(entry.path)

    add_subfolders(folder)
    names = []
    for path in folders:
        category = os.path.relpath(path, folder).replace(os.sep, "/")
        with os.scandir(path) as entries:
            for entry in entries:
                stem, ext = os.path.splitext(entry.name)
                if entry.is_file() and ext.lower() in WAVETABLE_EXTENSIONS:
                    names.append(stem if category == "." else f"{category}/{stem}")
    return names


@functools.lru_cache(maxsize=1)
def wavetable_ids() -> dict[str, int]:
    """{"Category/Name": id} for the factory wavetables, or {} if Surge's data
    folder isn't on this machine."""
    for folder in FACTORY_FOLDERS:
        if os.path.isdir(folder):
            return {name: idx for idx, name in enumerate(scan_wavetables(folder))}
    logger.warning("No Surge XT wavetables folder found in %s", FACTORY_FOLDERS)
    return {}


def wavetable_id(name: str) -> int | None:
    """Surge's id for the factory wavetable "Category/Name", or None."""
    idx = wavetable_ids().get(name)
    if idx is None:
        logger.warning("Wavetable %r not found", name)
    return idx
