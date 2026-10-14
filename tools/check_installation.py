"""Verify a folder-wrapped ZIP installs and starts from saved preferences."""

import argparse
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from build import build

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/validation"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--blender",
    default=os.environ.get("BLENDER_BIN")
    or shutil.which("blender")
    or "/Applications/Blender.app/Contents/MacOS/Blender",
)
args = parser.parse_args()
build()
OUT.mkdir(parents=True, exist_ok=True)
wrapped = OUT / "Folder_Zip.zip"
with (
    zipfile.ZipFile(ROOT / "dist/Base_Modeler.zip") as source,
    zipfile.ZipFile(wrapped, "w", zipfile.ZIP_DEFLATED) as archive,
):
    for name in source.namelist():
        archive.writestr("Base Modeler/" + name, source.read(name))
profile = ROOT / ".local/install_check"
profile.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.pop("PYTHONPATH", None)
env["PYTHONNOUSERSITE"] = "1"
env["BASE_MODELER_INSTALL_ZIP"] = str(wrapped)
for kind in ("CONFIG", "SCRIPTS", "DATAFILES", "EXTENSIONS"):
    path = profile / kind.lower()
    path.mkdir(exist_ok=True)
    env["BLENDER_USER_" + kind] = str(path)
commands = [
    (
        "folder_install",
        [
            args.blender,
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "tools/install_plugin.py"),
        ],
    ),
    (
        "installed_startup",
        [
            args.blender,
            "--background",
            str(ROOT / "examples/Base Modeler.blend"),
            "--disable-autoexec",
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "tools/verify_installed.py"),
        ],
    ),
]
for name, command in commands:
    with (OUT / (name + ".log")).open("w") as log:
        subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=120,
        )
    print(name + " passed", flush=True)
report = json.loads((OUT / "installed.json").read_text())
assert report["passed"]
report["folder_zip_installs"] = True
(OUT / "installed.json").write_text(json.dumps(report, indent=2) + "\n")
