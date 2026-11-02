"""Install and upgrade through Preferences > Get Extensions from a release listing.

Serves ``index.json`` from a ``file://`` repository, as GitHub serves it from the
latest release, and drives Blender's native sync, install and upgrade operators.
Run Blender with ``--online-mode``.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from build import parse_manifest, write_archive, write_index  # noqa: E402

PACKAGE = Path(os.environ.get("BASE_MODELER_PACKAGE", ROOT / "Base Modeler"))
MODULE = "bl_ext.bm_remote_test.base_modeler"
assert bpy.app.online_access, "Run with --online-mode"
manifest = parse_manifest((PACKAGE / "blender_manifest.toml").read_text())
major, minor, patch = map(int, manifest["version"].split("."))
newer = f"{major}.{minor}.{patch + 1}"
tmp = Path(tempfile.mkdtemp(prefix="base_modeler_repo_"))


def publish(version):
    archive = write_archive(PACKAGE, tmp / f"Base_Modeler-{version}.zip", version, 1)
    write_index(
        archive, dict(manifest, version=version), archive.as_uri(), tmp / "index.json"
    )


def installed_version():
    text = (Path(repo.directory) / "base_modeler" / "blender_manifest.toml").read_text()
    return parse_manifest(text)["version"]


try:
    prefs = bpy.context.preferences
    publish(manifest["version"])
    repo = prefs.extensions.repos.new(
        name="Base Modeler Releases",
        module="bm_remote_test",
        custom_directory=str(tmp / "installed"),
        remote_url=(tmp / "index.json").as_uri(),
    )
    index = list(prefs.extensions.repos).index(repo)
    assert bpy.ops.extensions.repo_sync(repo_index=index) == {"FINISHED"}
    assert bpy.ops.extensions.package_install(
        repo_index=index, pkg_id="base_modeler", enable_on_install=True
    ) == {"FINISHED"}
    assert MODULE in prefs.addons, list(prefs.addons.keys())
    assert installed_version() == manifest["version"]

    publish(newer)
    assert bpy.ops.extensions.repo_sync(repo_index=index) == {"FINISHED"}
    assert bpy.ops.extensions.package_upgrade_all() == {"FINISHED"}
    assert installed_version() == newer
    assert MODULE in prefs.addons
    assert sys.modules[MODULE].VERSION == (major, minor, patch + 1)
    bpy.ops.preferences.addon_disable(module=MODULE)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("EXTENSION REPOSITORY CHECK PASSED", flush=True)
