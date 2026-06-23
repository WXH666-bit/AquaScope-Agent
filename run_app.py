"""Launcher for AquaScope Streamlit app.

Patches starlette BEFORE streamlit is ever imported, then launches the app.
Use this instead of `streamlit run app.py` directly.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

# Patch starlette before streamlit touches it
import aquabio._patch_starlette  # noqa: F401, E402

# Launch streamlit as a subprocess so the patch applies in-process
import streamlit.web.cli as stcli  # noqa: E402

if __name__ == "__main__":
    sys.argv = [
        "streamlit",
        "run",
        str(ROOT / "app.py"),
        *sys.argv[1:],
    ]
    sys.exit(stcli.main())
