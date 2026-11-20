"""Import-time side effects of ``definitions.py``."""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_import_creates_user_config_folder_in_empty_home(tmp_path):
    """A fresh Lite image has no ~/.local/share; importing must not crash.

    Runs in a subprocess so the import-time constants of the already-imported
    ``definitions`` module in this test session aren't touched.
    """
    env = {**os.environ, "HOME": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-c", "import definitions"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".local" / "share" / "pushpin").is_dir()
