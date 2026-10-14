"""Install the built ZIP in the caller's isolated Blender profile."""

import bpy
import importlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
profile = Path(os.environ["BLENDER_USER_CONFIG"]).parent
repo = next(
    r for r in bpy.context.preferences.extensions.repos if r.module == "user_default"
)
assert Path(repo.directory).resolve().is_relative_to(profile.resolve())
archive = Path(
    os.environ.get("BASE_MODELER_INSTALL_ZIP", ROOT / "dist/Base_Modeler.zip")
)
assert bpy.ops.extensions.package_install_files(
    filepath=str(archive), repo=repo.module, enable_on_install=True
) == {"FINISHED"}
name = "bl_ext.user_default.base_modeler"
module = importlib.import_module(name)
assert name in bpy.context.preferences.addons
version = re.search(
    r'^version = "([^"]+)"',
    (ROOT / "Base Modeler/blender_manifest.toml").read_text(),
    re.M,
)[1]
installed_version = re.search(
    r'^version = "([^"]+)"',
    Path(module.__file__).with_name("blender_manifest.toml").read_text(),
    re.M,
)[1]
assert installed_version == version
assert Path(module.__file__).resolve().is_relative_to(profile.resolve())
if hasattr(bpy.context.preferences.view, "show_splash"):
    bpy.context.preferences.view.show_splash = False
bpy.ops.wm.save_userpref()
report = {
    "name": "Base Modeler",
    "version": version,
    "module": name,
    "installed_path": module.__file__,
    "enabled": True,
}
(ROOT / "artifacts/validation").mkdir(parents=True, exist_ok=True)
(ROOT / "artifacts/validation/install.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("BASE MODELER INSTALLED", json.dumps(report), flush=True)
