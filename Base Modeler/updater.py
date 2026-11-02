"""Check GitHub for newer Base Modeler releases and install them in place.

Every published release carries ``index.json``, a Blender extension repository
listing. The same file powers both update routes:

- Preferences > Get Extensions, after adding ``INDEX_URL`` as a remote repository.
- The Updates box in this add-on's preferences, which reads the listing, verifies the
  archive size and SHA-256 hash, and installs it with Blender's own installer into the
  repository this add-on already lives in.

Network access only happens on an explicit button press, or at startup when the
user leaves automatic checks on, and never while Blender's online access is off.
"""

import hashlib
import json
import os
import re
import tempfile
import threading
import time
import urllib.request
import zipfile

import bpy
from .constants import VERSION

GITHUB_REPO = "hokkaido-milk/Base-Modeler"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
INDEX_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/index.json"
PACKAGE_ID = "base_modeler"
ADDON = __package__
CHECK_INTERVAL = 24 * 3600
TIMEOUT = 30
INDEX_LIMIT = 1 << 20
ARCHIVE_LIMIT = 512 << 20

# Shared between worker threads and the main thread. Workers only write plain
# values; every bpy call stays on the main thread.
_STATE = {
    "status": "IDLE",  # IDLE CHECKING CURRENT AVAILABLE DOWNLOADING DOWNLOADED ERROR
    "message": "",
    "entry": None,
    "archive": None,
}
_LOCK = threading.Lock()


def _set(**values):
    with _LOCK:
        _STATE.update(values)


def state():
    with _LOCK:
        return dict(_STATE)


def version_tuple(text):
    """``"1.2.3"`` or ``"v1.2.3"`` to ``(1, 2, 3)``; ``None`` when malformed."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(text).strip())
    return tuple(map(int, match.groups())) if match else None


def version_text(version):
    return ".".join(map(str, version))


def pick_release(index, current=VERSION, blender=None):
    """Return ``(newest compatible entry, newest entry)`` newer than ``current``."""
    blender = tuple(blender or bpy.app.version)[:3]
    if not isinstance(index, dict) or not isinstance(index.get("data"), list):
        raise ValueError("Release listing is malformed")
    newer = []
    for entry in index["data"]:
        if not isinstance(entry, dict) or entry.get("id") != PACKAGE_ID:
            continue
        version = version_tuple(entry.get("version", ""))
        if version and version > tuple(current):
            newer.append((version, entry))
    newer.sort(key=lambda item: item[0], reverse=True)

    def compatible(entry):
        low = version_tuple(entry.get("blender_version_min", "0.0.0")) or (0, 0, 0)
        high = version_tuple(entry.get("blender_version_max", "")) or (999, 0, 0)
        return low <= blender < high

    usable = next((entry for _, entry in newer if compatible(entry)), None)
    return usable, newer[0][1] if newer else None


def _open(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"BaseModeler/{version_text(VERSION)} "
            f"Blender/{bpy.app.version_string.split()[0]}",
            "Accept": "application/json, application/octet-stream, */*",
        },
    )
    return urllib.request.urlopen(request, timeout=TIMEOUT)


def fetch_index(url=None):
    with _open(url or INDEX_URL) as response:
        data = response.read(INDEX_LIMIT + 1)
    if len(data) > INDEX_LIMIT:
        raise ValueError("Release listing is unexpectedly large")
    return json.loads(data.decode("utf-8"))


def _manifest_field(text, key):
    match = re.search(rf'^{key}\s*=\s*"([^"]*)"\s*$', text, re.M)
    return match[1] if match else None


def download(entry, directory):
    """Download and verify ``entry``'s archive; return the local ZIP path."""
    url = entry.get("archive_url", "")
    size = entry.get("archive_size")
    digest = str(entry.get("archive_hash", "")).lower()
    if not url.startswith(("https://", "file://")):
        raise ValueError("Release archive URL is not HTTPS")
    if not digest.startswith("sha256:") or not isinstance(size, int):
        raise ValueError("Release listing has no archive size or SHA-256 hash")
    if not 0 < size <= ARCHIVE_LIMIT:
        raise ValueError("Release archive size is out of range")
    path = os.path.join(directory, f"Base_Modeler-{entry['version']}.zip")
    sha = hashlib.sha256()
    received = 0
    with _open(url) as response, open(path, "wb") as out:
        while chunk := response.read(1 << 16):
            received += len(chunk)
            if received > size:
                raise ValueError("Downloaded archive is larger than listed")
            sha.update(chunk)
            out.write(chunk)
    if received != size:
        raise ValueError("Download was incomplete")
    if "sha256:" + sha.hexdigest() != digest:
        raise ValueError("Downloaded archive failed its SHA-256 check")
    with zipfile.ZipFile(path) as archive:
        manifest = archive.read("blender_manifest.toml").decode("utf-8")
    if _manifest_field(manifest, "id") != PACKAGE_ID:
        raise ValueError("Downloaded archive is not Base Modeler")
    if _manifest_field(manifest, "version") != entry["version"]:
        raise ValueError("Downloaded archive version does not match the listing")
    return path


def current_repo():
    """Return the extension repository this add-on is installed in, or ``None``."""
    parts = ADDON.split(".")
    if len(parts) != 3 or parts[0] != "bl_ext":
        return None
    for repo in bpy.context.preferences.extensions.repos:
        if repo.module == parts[1] and repo.enabled and repo.source != "SYSTEM":
            return repo
    return None


def can_go_online():
    return bool(bpy.app.online_access)


def _prefs():
    addon = bpy.context.preferences.addons.get(ADDON)
    return addon.preferences if addon else None


# ---------------------------------------------------------------------------
# Background work and main-thread hand-off


def _check_worker(url):
    try:
        usable, newest = pick_release(fetch_index(url))
    except Exception as ex:  # Network and listing errors are user-facing.
        _set(status="ERROR", message=f"Update check failed: {ex}", entry=None)
        return
    if usable:
        _set(status="AVAILABLE", message="", entry=usable)
    elif newest:
        _set(
            status="CURRENT",
            entry=None,
            message=f"Version {newest['version']} needs Blender "
            f"{newest.get('blender_version_min', '?')} or newer.",
        )
    else:
        _set(status="CURRENT", message="", entry=None)


def _download_worker(entry):
    try:
        directory = tempfile.mkdtemp(prefix="base_modeler_update_")
        _set(status="DOWNLOADED", archive=download(entry, directory))
    except Exception as ex:
        _set(status="ERROR", message=f"Download failed: {ex}")


def _redraw():
    wm = getattr(bpy.context, "window_manager", None)
    for window in wm.windows if wm else ():
        for area in window.screen.areas:
            if area.type in {"PREFERENCES", "VIEW_3D"}:
                area.tag_redraw()


def _poll():
    """Main-thread timer: redraw while busy, then install a finished download."""
    if ADDON not in bpy.context.preferences.addons:
        return None  # Disabled while working; leave the files alone.
    _redraw()
    current = state()
    if current["status"] in {"CHECKING", "DOWNLOADING"}:
        return 0.25
    if current["status"] == "DOWNLOADED":
        install(current["archive"])
    return None


def _start(status, target, *args):
    _set(status=status, message="")
    threading.Thread(target=target, args=args, daemon=True).start()
    if not bpy.app.timers.is_registered(_poll):
        bpy.app.timers.register(_poll, first_interval=0.25)


def start_check(url=None):
    prefs = _prefs()
    if prefs is not None:
        prefs.last_check = time.time()
    _start("CHECKING", _check_worker, url)


def start_install():
    entry = state()["entry"]
    if entry is None:
        raise RuntimeError("No update is available")
    _start("DOWNLOADING", _download_worker, entry)


def install(path):
    """Install a verified archive into this add-on's repository (main thread).

    Blender's installer disables the running add-on, replaces its files and
    enables the new version, so this module is unloaded during the call.
    """
    repo = current_repo()
    try:
        if repo is None:
            raise RuntimeError("Base Modeler is not installed as an extension")
        windows = bpy.context.window_manager.windows
        override = {"window": windows[0]} if windows else {}
        with bpy.context.temp_override(**override):
            result = bpy.ops.extensions.package_install_files(
                filepath=path, repo=repo.module, enable_on_install=True
            )
        if "FINISHED" not in result:
            raise RuntimeError("Blender did not finish installing the update")
    except Exception as ex:
        _set(status="ERROR", message=f"Install failed: {ex}")
        return False
    finally:
        try:
            os.remove(path)
            os.rmdir(os.path.dirname(path))
        except OSError:
            pass
    _set(status="IDLE", entry=None, archive=None)
    _announce()
    return True


def _announce():
    def draw(menu, _context):
        menu.layout.label(text="The new version is active now.")
        menu.layout.label(text="Restart Blender to finish the update.")

    wm = bpy.context.window_manager
    if wm.windows and not bpy.app.background:
        with bpy.context.temp_override(window=wm.windows[0]):
            wm.popup_menu(draw, title="Base Modeler updated", icon="INFO")
    print("Base Modeler: update installed; restart Blender to finish.", flush=True)


def _startup_check():
    prefs = _prefs()
    if (
        prefs is not None
        and prefs.auto_check
        and can_go_online()
        and time.time() - prefs.last_check > CHECK_INTERVAL
        and state()["status"] == "IDLE"
    ):
        start_check()
    return None


def update_available():
    return state()["status"] == "AVAILABLE"


# ---------------------------------------------------------------------------
# Operators and preferences


class BM_OT_update_check(bpy.types.Operator):
    """Look for a newer Base Modeler release on GitHub"""

    bl_idname = "base_modeler.update_check"
    bl_label = "Check for Updates"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, _context):
        if not can_go_online():
            cls.poll_message_set("Allow online access in Preferences > System")
            return False
        return state()["status"] not in {"CHECKING", "DOWNLOADING", "DOWNLOADED"}

    def execute(self, _context):
        start_check()
        return {"FINISHED"}


class BM_OT_update_install(bpy.types.Operator):
    """Download the newer release, verify it and install it in place"""

    bl_idname = "base_modeler.update_install"
    bl_label = "Install Update"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, _context):
        if not can_go_online():
            cls.poll_message_set("Allow online access in Preferences > System")
            return False
        if current_repo() is None:
            cls.poll_message_set("Base Modeler is not installed as an extension")
            return False
        return update_available()

    def invoke(self, context, event):
        version = state()["entry"]["version"]
        return context.window_manager.invoke_confirm(
            self,
            event,
            title=f"Install Base Modeler {version}?",
            message="Save your work first. Restart Blender after the update.",
            confirm_text="Install",
        )

    def execute(self, _context):
        start_install()
        return {"FINISHED"}


class BM_OT_update_copy_url(bpy.types.Operator):
    """Copy the repository URL for Preferences > Get Extensions"""

    bl_idname = "base_modeler.update_copy_url"
    bl_label = "Copy Repository URL"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        context.window_manager.clipboard = INDEX_URL
        self.report({"INFO"}, "Copied " + INDEX_URL)
        return {"FINISHED"}


class BM_OT_update_show(bpy.types.Operator):
    """Open Base Modeler's preferences to review the available update"""

    bl_idname = "base_modeler.update_show"
    bl_label = "Show Update"
    bl_options = {"INTERNAL"}

    def execute(self, _context):
        bpy.ops.preferences.addon_show(module=ADDON)
        return {"FINISHED"}


class BM_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON

    auto_check: bpy.props.BoolProperty(
        name="Check for Updates Automatically",
        description="Look for a new release once a day when Blender starts. "
        "Requires online access",
        default=True,
    )
    last_check: bpy.props.FloatProperty(options={"HIDDEN"}, default=0.0)

    def draw(self, _context):
        current = state()
        box = self.layout.box()
        box.label(text="Updates", icon="FILE_REFRESH")
        col = box.column()
        col.label(text=f"Installed version: {version_text(VERSION)}")
        status = current["status"]
        if not can_go_online():
            col.label(
                text="Online access is off. Allow it in Preferences > System.",
                icon="INFO",
            )
        elif status == "CHECKING":
            col.label(text="Checking GitHub…", icon="SORTTIME")
        elif status in {"DOWNLOADING", "DOWNLOADED"}:
            col.label(text="Downloading and installing…", icon="SORTTIME")
        elif status == "AVAILABLE":
            col.label(
                text=f"Version {current['entry']['version']} is available.",
                icon="IMPORT",
            )
        elif status == "CURRENT":
            col.label(text="You have the latest version.", icon="CHECKMARK")
        if current["message"]:
            col.label(
                text=current["message"],
                icon="ERROR" if status == "ERROR" else "INFO",
            )
        row = box.row()
        row.operator("base_modeler.update_check", icon="FILE_REFRESH")
        if status == "AVAILABLE":
            row.operator(
                "base_modeler.update_install",
                text=f"Install {current['entry']['version']}",
                icon="IMPORT",
            )
            if current_repo() is None:
                box.label(
                    text="Loaded outside an extension repository; "
                    "download the release manually.",
                    icon="INFO",
                )
        row.operator("wm.url_open", text="Release Notes", icon="URL").url = RELEASES_URL
        box.prop(self, "auto_check")

        box = self.layout.box()
        box.label(text="Get Extensions repository", icon="WORLD")
        col = box.column(align=True)
        col.label(text="Add this URL as a remote repository in Preferences >")
        col.label(text="Get Extensions to install and update Base Modeler there.")
        row = box.row(align=True)
        row.label(text=INDEX_URL)
        row.operator("base_modeler.update_copy_url", text="", icon="COPYDOWN")


CLASSES = (
    BM_OT_update_check,
    BM_OT_update_install,
    BM_OT_update_copy_url,
    BM_OT_update_show,
    BM_AddonPreferences,
)


def register():
    if not bpy.app.background and not bpy.app.timers.is_registered(_startup_check):
        bpy.app.timers.register(_startup_check, first_interval=5.0)


def unregister():
    # ``_poll`` is not removed here: it may be the caller, installing an update,
    # and it stops by itself once this add-on is no longer enabled.
    if bpy.app.timers.is_registered(_startup_check):
        bpy.app.timers.unregister(_startup_check)
