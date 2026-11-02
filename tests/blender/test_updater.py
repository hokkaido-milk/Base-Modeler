"""In-place update from the add-on preferences, end to end with local files.

Installs the package into a throwaway extension repository, publishes a newer
build through a ``file://`` release listing and lets the add-on's updater find,
verify and install it with Blender's own installer.
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
MODULE = "bl_ext.bm_update_test.base_modeler"
manifest = parse_manifest((PACKAGE / "blender_manifest.toml").read_text())
current = tuple(map(int, manifest["version"].split(".")))
newer = f"{current[0]}.{current[1]}.{current[2] + 1}"
tmp = Path(tempfile.mkdtemp(prefix="base_modeler_update_"))
try:
    prefs = bpy.context.preferences
    (tmp / "repo").mkdir()
    repo = prefs.extensions.repos.new(
        name="Updater Test", module="bm_update_test", custom_directory=str(tmp / "repo")
    )
    assert repo.directory == str(tmp / "repo"), repo.directory
    old = write_archive(PACKAGE, tmp / "old.zip", level=1)
    assert bpy.ops.extensions.package_install_files(
        filepath=str(old), repo=repo.module, enable_on_install=True
    ) == {"FINISHED"}
    assert MODULE in prefs.addons, list(prefs.addons.keys())
    installed = sys.modules[MODULE]
    up = installed.updater
    assert installed.VERSION == current
    assert up.ADDON == MODULE and up.current_repo().module == repo.module
    assert prefs.addons[MODULE].preferences.auto_check
    assert "update_check" in dir(bpy.ops.base_modeler)

    # Version parsing and release selection.
    assert up.version_tuple("v1.10.2") == (1, 10, 2)
    assert up.version_tuple("1.2") is None and up.version_tuple("1.2.3-rc") is None
    listing = {
        "version": "v1",
        "data": [
            {"id": "other", "version": "99.0.0"},
            {"id": "base_modeler", "version": "1.2.0"},
            {"id": "base_modeler", "version": "1.4.0", "blender_version_min": "5.2.0"},
            {"id": "base_modeler", "version": "2.0.0", "blender_version_min": "6.0.0"},
        ],
    }
    usable, newest = up.pick_release(listing, (1, 3, 0), (5, 2, 2))
    assert usable["version"] == "1.4.0" and newest["version"] == "2.0.0"
    assert up.pick_release(listing, (2, 0, 0), (5, 2, 2)) == (None, None)
    for bad in ({}, {"data": "x"}, []):
        try:
            up.pick_release(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Malformed listing accepted")

    # Publish a newer build and check for it.
    new = write_archive(PACKAGE, tmp / "new.zip", version=newer, level=1)
    new_manifest = dict(manifest, version=newer)
    index = write_index(new, new_manifest, new.as_uri(), tmp / "index.json")
    up.INDEX_URL = index.as_uri()
    up._check_worker(None)
    state = up.state()
    assert state["status"] == "AVAILABLE", state
    assert state["entry"]["version"] == newer and up.update_available()

    # Verification rejects tampered, oversized and non-HTTPS listings.
    work = tmp / "downloads"
    work.mkdir()
    entry = state["entry"]
    for bad in (
        dict(entry, archive_hash="sha256:" + "0" * 64),
        dict(entry, archive_size=entry["archive_size"] - 1),
        dict(entry, archive_url="http://example.invalid/Base_Modeler.zip"),
        dict(entry, version="9.9.9"),
    ):
        try:
            up.download(bad, str(work))
        except ValueError:
            pass
        else:
            raise AssertionError(f"Unverified archive accepted: {bad}")

    # Install in place: Blender reloads the add-on from the new files.
    path = up.download(entry, str(work))
    assert up.install(path) is True, up.state()
    assert not os.path.exists(path)
    assert MODULE in prefs.addons
    updated = sys.modules[MODULE]
    assert updated is not installed
    assert updated.VERSION == tuple(map(int, newer.split(".")))
    on_disk = (Path(repo.directory) / "base_modeler" / "blender_manifest.toml").read_text()
    assert parse_manifest(on_disk)["version"] == newer
    assert updated.updater.state()["status"] == "IDLE"

    # The newer version sees no further update in the same listing.
    updated.updater.INDEX_URL = index.as_uri()
    updated.updater._check_worker(None)
    assert updated.updater.state()["status"] == "CURRENT", updated.updater.state()

    bpy.ops.preferences.addon_disable(module=MODULE)
    assert MODULE not in prefs.addons
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("UPDATER CHECK PASSED", flush=True)
