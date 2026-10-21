# Release audit

The shipping extension is **Base Modeler 1.1.0**. Its runtime source is
`Base Modeler/`; `dist/Base_Modeler.zip` is built from that folder without
changing its contents. The source contains current usage documentation,
required asset provenance and the complete code license. Development history,
old packages and authoring references are kept in the ignored local archive.

## Structure and fixes

- Registration, model state, undoable operators and sidebar drawing are separate
  modules. The public entry point retains the existing helper interfaces.
- Stable anatomical region IDs keep deformation and rig bindings intact after
  object or mesh renaming. Region order no longer depends on display names.
- Failed shape updates restore applied slider values and any uploaded mesh
  coordinates. Failed creation removes only newly appended data and preserves
  existing objects, selection and unrelated unused user data.
- Reset scopes are validated. Reset All resynchronizes actual mesh coordinates
  so it also restores manual vertex moves when all sliders are already neutral.
- Partial registration rolls back classes, handlers and properties. Unregister
  tolerates partial state. Older saved-model migration retains custom settings.
- Rig removal tolerates missing or malformed stored group-name metadata while
  preserving unrelated vertex groups.
- Limb joints fit closed skin cross sections, with corresponding mesh edges
  carrying the fit through changes in body proportions. Wrist and palm centers
  follow the hand's actual offset; knees, ankles and toe stations are corrected.
  Wrist, knee and toe weight transitions now match those joint positions.
- Existing rigs retain their saved rest positions and poses. The sidebar flags
  older bindings for removal and regeneration to apply the corrected fit.
- Each hand has 15 digit bones, and each foot has 14. Skin sections fit their
  joints; local X curls toward the palm or sole. Five bone collections separate
  the body and each hand/foot. Slim bone displays use actual skin clearance,
  avoiding an octahedral shaft protruding through a narrow forearm.
- Digit binding follows skin-edge distances from terminal caps, with a smooth
  partition at webs and local capsule/thenar support. Seeds cannot jump to a
  neighbouring toe across an air gap. Joint blends limit peak weight gradients;
  rigid nail plates follow distal phalanges. Binary weight fractions improve
  precision, and sorted uploads avoid scanning a complete mesh per weight value.
- Native interpolation validates array dimensions and finite coordinates before
  entering C. NumPy remains a functional fallback.
- Height-only edits reuse the evaluated raw shape rather than reintegrating
  deformation fields. Deleted model caches are pruned on subsequent cache builds.

## Data cleanup

The foundation and example retain 29 meshes, 271,342 vertices, 32 used materials
and one packed face texture. Cameras, lights, armatures, animation actions,
embedded text blocks, unused materials, unused source vertex groups, unused
shader groups, development notes and old texture directory paths are removed.
Only functional binding/settings metadata remains. The procedural skin material
still uses immutable rest coordinates. Unused sculpt debug arrays are removed.
Blender can create transient Render Result/Viewer buffers when opening a main
file; these are not shipped textures.

The example is an editable body in lit EEVEE Material Preview. The plugin does
not change the user's viewport theme or shading. The native macOS accelerator
is rebuilt from the included C source, with an independent library name and
release metadata. The asset format requires Blender 5.2 or newer.

## Verification

Validated in Blender 5.2.2 LTS on Apple Silicon macOS. Reports are generated
under `artifacts/validation/` and are excluded from Git.

| Check | Result |
| --- | --- |
| Pre-refactor geometry comparison | 119 cases; identical coordinates |
| Packaged shape sweep | 151 endpoint, combined and mixed cases pass |
| Regional seams / triangle collapse | Exact shared borders; no collapsed valid source triangles |
| Reset / length isolation | All 27 field resets, 13 region resets, Reset All and height limits pass |
| Failure and rename cases | Update, creation and registration rollback; renamed objects and rig pass |
| Native / NumPy comparison | 17 mixed cases; maximum measured difference 0 m |
| Undo / redo | Shape edits, linked length/Height edits and rig lifecycle pass |
| Bone audit | All 80 bones translated and rotated about all three axes in both directions |
| Limb/digit fitting | 31 proportion cases; 29,140 sampled axis points inside skin; joined chain endpoints |
| Forearm posing | 162 cases across neutral, short/thin and long/thin bodies; axis and displayed shaft inside own-arm skin |
| Digit posing | 58 individual bends; 20 rigid nail plates; neighbouring nails isolated; seams/reset pass |
| Wrist stress | Both hands, three axes, ±60°; palms/nails follow; opposite hand unchanged; seams/reset pass |
| Seated pose | No collapsed valid faces; seam/reset checks pass |
| Saved files | Editable controls and length scale reopen correctly; native rig poses without plugin |
| Materials | Source-pattern and height render comparisons pass |
| Installation | Content ZIP and enclosing-folder ZIP install; saved startup and disable/re-enable pass |
| Quality | Black formatting and Ruff lint checks pass |

The packaged suite uses isolated Blender configuration, scripts, data and
extension directories to prevent locally installed addons from affecting
save/reopen checks. The installed preview was also inspected interactively with
finger curls. The rig remains native Blender data without addon pose handlers.

Strong curls retain small compressed faces along the inside crease. The digit
test bounds their combined source area to 10 mm² per pose and rejects near-zero
faces. The measured tight curl compresses two faces covering about 1.8 mm².
These checks do not certify collision-free fists or prevent a lowered arm from
intersecting the torso; pose-specific corrective sculpting is not included.

Measured callback median: approximately 19 ms across the shape sweep and 8 ms
for height-only edits. These headless measurements exclude interactive viewport
rendering and depend on hardware. The sculpt remains a stylized anatomical
foundation; sampled checks do not certify every shape/pose or eliminate all
existing intersections in extreme combinations. Other Blender versions and
non-macOS platforms have not been exercised.

## Publishing

The code is GPL-3.0-or-later. The supplied model, materials, texture and reference
archives have no documented upstream redistribution license. Their provenance
is retained in `Base Modeler/NOTICES.md`; confirm asset redistribution rights
before publishing the bundled assets publicly.
