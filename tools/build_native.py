"""Rebuild the optional universal macOS accelerator from its shipped C source."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "Base Modeler"
if sys.platform != "darwin":
    raise SystemExit("This optional binary is for macOS; other platforms use NumPy.")
version = re.search(
    r'^version = "([^"]+)"', (PACKAGE / "blender_manifest.toml").read_text(), re.M
)[1]
subprocess.run(
    [
        "clang",
        "-O3",
        "-ffp-contract=off",
        "-arch",
        "arm64",
        "-arch",
        "x86_64",
        "-dynamiclib",
        "-install_name",
        "@rpath/libbase_modeler_flow.dylib",
        "-current_version",
        version,
        "-compatibility_version",
        "1.0.0",
        str(PACKAGE / "native/flow.c"),
        "-o",
        str(PACKAGE / "native/libbase_modeler_flow.dylib"),
    ],
    check=True,
)
print("Built universal macOS accelerator", flush=True)
