"""Run the Blender regression suite against the built ZIP in a temporary directory."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
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
parser.add_argument(
    "--full",
    action="store_true",
    help="Also run the rendered material-stability check.",
)
args = parser.parse_args()
archive = build()
OUT.mkdir(parents=True, exist_ok=True)
checks = []
with tempfile.TemporaryDirectory(prefix="base_modeler_checks_") as tmp:
    package = Path(tmp) / "base_modeler"
    package.mkdir()
    with zipfile.ZipFile(archive) as z:
        z.extractall(package)
    env = os.environ.copy()
    env["BASE_MODELER_PACKAGE"] = str(package)
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    # Saved-file checks must not inherit extensions enabled in the user's
    # normal profile, especially the test that proves rig independence.
    for kind in ("CONFIG", "SCRIPTS", "DATAFILES", "EXTENSIONS"):
        path = Path(tmp) / "profile" / kind.lower()
        path.mkdir(parents=True, exist_ok=True)
        env["BLENDER_USER_" + kind] = str(path)

    def run(name, script, file=None, load=True, extra=()):
        command = [args.blender, "--background"]
        command += [str(file)] if file else ["--factory-startup"]
        command += ["--disable-autoexec", "--python-exit-code", "1"]
        if load:
            command += ["--python", str(ROOT / "tools/load_plugin.py")]
        command += ["--python", str(ROOT / "tests/blender" / script)]
        command += list(extra)
        start = time.monotonic()
        with (OUT / (name + ".log")).open("w") as log:
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=300,
            )
        record = {
            "name": name,
            "passed": result.returncode == 0,
            "seconds": round(time.monotonic() - start, 2),
        }
        checks.append(record)
        print(json.dumps(record), flush=True)
        if result.returncode:
            print((OUT / (name + ".log")).read_text()[-5000:], flush=True)
            raise SystemExit("Check failed: " + name)

    run("assets", "test_assets.py", load=False)
    run("shapes", "test_shapes.py")
    run("controls", "test_controls.py")
    run("runtime", "test_runtime.py")
    run("undo", "test_undo.py")
    run("torso", "test_torso.py")
    run("breast_shape", "test_breast_shape.py")
    run("surfaces", "test_surfaces.py")
    run("joint_fit", "test_joint_fit.py")
    run("wrist_pose", "test_wrist_pose.py")
    run("forearm_pose", "test_forearm_pose.py")
    run("digits", "test_digits.py")
    run("anatomy_rig", "test_anatomy_rig.py")
    run("spine_pose", "test_spine_pose.py")
    run("poses", "test_poses.py")
    run("rig", "test_rig.py")
    run("rig_reopen", "test_rig_reopen.py", OUT / "rig/Native_Rig.blend", load=False)
    run("reopen", "test_reopen.py", OUT / "Editable.blend")
    run("persistence", "test_persistence.py")
    run(
        "persistence_reopen",
        "test_persistence.py",
        OUT / "Length_Persistence.blend",
        extra=("--", "--reopen"),
    )
    if args.full:
        run("materials", "test_materials.py")
report = {
    "package": archive.name,
    "package_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    "checks": checks,
    "passed": all(c["passed"] for c in checks),
}
(OUT / "suite.json").write_text(json.dumps(report, indent=2) + "\n")
print("ALL CHECKS PASSED", flush=True)
