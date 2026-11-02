# BaseModelGen: project context

_Gathered 2026-11-02 from the working tree at commit `4801ad3` (main, clean)._

## What it is

**Base Modeler** (v1.3.0) is a Blender 5.2+ extension (add-on) for making a stylized
adult anime female base body as a drawing / posing reference. It:

- Creates a base model from a bundled foundation mesh (29 meshes, ~271k verts, packed face texture).
- Exposes **27 continuous shape controls** (height 120-200 cm, torso/leg ratio, build,
  breast/butt/hip/thigh/leg/arm/hand/foot/head controls, etc.) in the N-panel sidebar.
- Generates a native **83-bone FK rig** (81 controls + 2 hidden forearm twist bones), with
  joint rotation limits, per-finger/toe bones, bone collections, custom widgets, and
  computed skin weights. Rigs stay poseable without the add-on installed.
- Optional **pose target balls** (IK hands/feet, look-at head) with IK/FK switching.
- No pip deps or Rigify. Optional GitHub update check (`updater.py`), honouring online access. Uses Blender's bundled NumPy, plus an optional
  universal macOS C accelerator (`native/flow.c` -> `libbase_modeler_flow.dylib`).

Remote: `https://github.com/hokkaido-milk/Base-Modeler.git`. License: GPL-3.0-or-later for
code. **Asset redistribution rights are unconfirmed** (see `Base Modeler/NOTICES.md`).

## Layout

| Path | What |
| --- | --- |
| `Base Modeler/` | The single plugin source (the shipped package). `blender_manifest.toml`, user README, NOTICES, LICENSE |
| `Base Modeler/assets/` | `foundation.blend/.json` + sculpt/contact/partition `.npz` arrays (vertex-index aligned) |
| `Base Modeler/native/` | Optional C kernel + macOS dylib + Python loader with NumPy fallback |
| `tools/` | Build, install, preview, asset refresh and check scripts (19) |
| `tests/blender/` | 28 Blender-run regression tests |
| `docs/` | `DEVELOPMENT.md` (dev guide), `AUDIT.md` (release audit), `WEIGHT_REVIEW.md` (joint limits/weights), `ANATOMY_REVIEW.md`, `TARGET_CONTROLS.md` |
| `examples/Base Modeler.blend` | Editable example scene |
| `dist/` | Built `Base_Modeler.zip` + sha256 (gitignored) |
| `artifacts/` | Validation reports, before/after renders, probe scripts per work pass (gitignored) |
| `.archive/`, `.local/` | Old dev history and local tooling/Blender profile (gitignored) |

### Plugin modules (~3.3k lines Python)

| Module | Role |
| --- | --- |
| `__init__.py` | Registration, public helper exports |
| `constants.py`, `identity.py` | Version, schema IDs, stable region IDs |
| `controls.py` | The 27 control definitions, groups, defaults |
| `model.py` | `BM_Settings`, per-model state/cache, update pipeline, saved-file migration |
| `deform.py`, `sculpt.py`, `surface.py`, `contact.py`, `fitting.py`, `topology.py`, `library.py` | Shape deformation fields, anatomy sculpt, surface contacts, joint fitting, tessellation repair, asset loading |
| `rig.py` (largest, ~750 lines) | Rig generation, binding, weights |
| `digits.py`, `limits.py`, `pose.py` | Finger/toe bones and weights, joint limits, posing |
| `targets.py`, `widgets.py` | IK target balls and bone widgets |
| `operators.py`, `ui.py` | Undoable operators and sidebar panels |

## How to run

```sh
python3 tools/build.py                 # deterministic dist/Base_Modeler.zip + sha256
python3 tools/build_native.py          # macOS only: rebuild optional C accelerator
python3 tools/run_checks.py --full     # build, extract, run every test in fresh isolated Blender
python3 tools/open_blender.py [file]   # install into isolated .local/blender profile and open example
python3 -m black 'Base Modeler' tools tests && python3 -m ruff check 'Base Modeler' tools tests
```

Blender binary: `--blender PATH`, `BLENDER_BIN`, `blender` on PATH, or
`/Applications/Blender.app/Contents/MacOS/Blender`. Reports land in `artifacts/validation/`.
Asset refresh commands (foundation cleanup, example regen, `refine_anatomy.py`,
`remove_face_shells.py`) are in `docs/DEVELOPMENT.md`.

End-user install: Preferences > Get Extensions > add remote repository `https://github.com/hokkaido-milk/Base-Modeler/releases/latest/download/index.json`, or Install from Disk with `dist/Base_Modeler.zip`. Release: `python3 tools/release.py [--publish]` (assets: zip, sha256, index.json).

## Current state

- 10 commits, latest `4801ad3 refine rig controls` (2026-10-27). Working tree clean.
- Last recorded suite (`artifacts/validation/suite.json`): **29/29 checks passed**.
- Recent work arc: rig fix -> hand/foot digit bones -> rig refinement -> spine weight
  fix -> anatomy/breast/butt refinement -> pose target controls and widgets.
- No `TODO`/`FIXME` markers in code.

## Known limitations / open items (from docs)

- Asset licensing: foundation mesh/materials/texture came from a user-supplied file with no
  upstream license; confirm before publishing.
- Only tested on Blender 5.2.2, Apple Silicon macOS. Other platforms untested (NumPy path).
- FK rig without IK on the base rig (IK only via optional target balls); no corrective
  shapes or collision handling, so strong finger/toe curls and extreme poses can crease.
- Existing saved rigs keep old binding after plugin updates; must remove and regenerate.
- Changing topology or deleting body parts invalidates slider editing.
- Target IK: dragging past full extension is abrupt; unreachable targets separate.
