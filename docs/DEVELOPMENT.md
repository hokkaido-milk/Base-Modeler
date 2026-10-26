# Development

`Base Modeler/` is the single plugin source. Do not maintain a second runtime copy.
Blender supplies `bpy` and NumPy; the plugin has no pip or network dependencies.
The only shipped native binary is an optional universal macOS accelerator, with
its C source alongside it. Other platforms use the NumPy implementation.

## Build

```sh
python3 tools/build.py
```

This validates the package identity/version and produces a deterministic
`dist/Base_Modeler.zip` plus a SHA-256 file. ZIP entries are relative to the
plugin root. Finder-style archives containing the enclosing folder also install.
No caches, backups, local profiles, tests or development archives are bundled.

On macOS, rebuild the optional native kernel with:

```sh
python3 tools/build_native.py
```

Python code formatting/lint tools are optional development dependencies:

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m black 'Base Modeler' tools tests
python3 -m ruff check 'Base Modeler' tools tests
```

## Validate

```sh
python3 tools/run_checks.py --full
```

The suite builds and extracts the ZIP to a temporary directory, then runs each
check in a fresh Blender process with isolated user directories. Use
`--blender /path/to/blender` or set
`BLENDER_BIN` on another installation. Reports and logs go to `artifacts/validation/`.
`--full` includes rendered source-pattern and height material-stability checks.

## Refresh assets and example

Run these only on the generated foundation/environment, since cleanup removes
unrelated scene objects and unused data:

```sh
blender --background --factory-startup 'Base Modeler/assets/foundation.blend' --disable-autoexec --python-exit-code 1 --python tools/load_plugin.py --python tools/clean_assets.py
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/load_plugin.py --python tools/prepare_example.py
```

On macOS the Blender executable is normally
`/Applications/Blender.app/Contents/MacOS/Blender`.
The foundation retains immutable A-pose rest coordinates and displays the
neutral T-pose. Sculpt/attachment arrays use stable region order and vertex
indices; regenerate them when replacing source geometry. Internal data-schema
identifiers support saved-model compatibility and are independent of the public
release version.

`tools/remove_face_shells.py` deletes the eyebrow, eyelid-line and eyelash
shells from the head (they float above finished skin). It keeps their vertices
as loose points so vertex-indexed assets stay aligned, and is idempotent. Run it
after `load_plugin.py` and before `clean_assets.py` in the foundation refresh
command above.

`tools/refine_anatomy.py` rebuilds `assets/anatomy_sculpt.npz` from immutable
rest coordinates plus the earlier foundation corrections. Run it through
Blender after `tools/load_plugin.py`. It deliberately bypasses its own output,
so rebuilding never accumulates sculpt offsets. The pass preserves topology
and operates before controls, contact fitting and rig weight generation.
Run `test_anatomy_surface.py` and the full suite after rebuilding; then refresh
the foundation and editable example using the commands above. See
`docs/ANATOMY_REVIEW.md` for the artistic scope and reference sources.

## Preview installed package

```sh
python3 tools/open_blender.py
```

This macOS helper builds and installs the ZIP into `.local/blender/`, saves its
preferences, and opens the clean example in a new instance. It does not change
the user's main Blender profile. The startup check verifies that the installed
extension enabled from saved preferences. Viewport defaults are lit Material
Preview with the Base Modeler sidebar visible.

Pass a `.blend` path to open a different file in that isolated profile. To
prepare and inspect a neutral rig with a full-body view with the core control selected:

```sh
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/load_plugin.py --python tools/prepare_rig_preview.py
python3 tools/open_blender.py 'artifacts/rig_refinement/Base Modeler Rig.blend'
```
