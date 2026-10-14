"""Install and open Base Modeler in an isolated persistent macOS Blender profile."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / ".local/blender"
if sys.platform != "darwin":
    raise SystemExit(
        "For other platforms, install dist/Base_Modeler.zip through Blender Preferences."
    )
model = ROOT / "examples/Base Modeler.blend"
if not model.is_file():
    raise SystemExit(
        "Generate examples/Base Modeler.blend first; see docs/DEVELOPMENT.md."
    )
subprocess.run([sys.executable, str(ROOT / "tools/build.py")], check=True)
PROFILE.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env.pop("PYTHONPATH", None)
env["PYTHONNOUSERSITE"] = "1"
profile_env = {}
for kind in ("CONFIG", "SCRIPTS", "DATAFILES", "EXTENSIONS"):
    path = PROFILE / kind.lower()
    path.mkdir(exist_ok=True)
    profile_env["BLENDER_USER_" + kind] = str(path)
env.update(profile_env)
blender = "/Applications/Blender.app/Contents/MacOS/Blender"
with (PROFILE / "install.log").open("w") as log:
    subprocess.run(
        [
            blender,
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "tools/install_plugin.py"),
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        check=True,
        timeout=120,
    )
command = [
    "/usr/bin/open",
    "-n",
    "-a",
    "/Applications/Blender.app",
    "--stdout",
    str(PROFILE / "session.log"),
    "--stderr",
    str(PROFILE / "session.log"),
]
for key, value in {**profile_env, "PYTHONNOUSERSITE": "1"}.items():
    command.extend(["--env", key + "=" + value])
command.extend(
    [
        "--args",
        "--disable-autoexec",
        str(model),
        "--python",
        str(ROOT / "tools/show_session.py"),
    ]
)
subprocess.run(command, cwd=ROOT, check=True)
print("Opened Blender with Base Modeler installed", flush=True)
