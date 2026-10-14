# Base Modeler

Shape an adult anime body with 27 continuous controls, then generate a native
22-bone FK rig for posing. The foundation, anatomy corrections and face texture
are bundled. No external generator, Rigify or network access is required.

## Install

Requires Blender 5.2 or newer. Tested with Blender 5.2.2 LTS on Apple Silicon macOS.
The optional macOS accelerator includes arm64 and x86_64 binaries. Other platforms
use the NumPy implementation included with Blender; they have not been tested.

Zip this folder's contents, including `blender_manifest.toml`, or use the supplied
`Base_Modeler.zip`. In Blender, choose **Edit → Preferences → Add-ons → Install
from Disk**, select the ZIP and enable **Base Modeler**.

## Use

1. In the 3D View, press **N** and open **Base Modeler**.
2. Choose **Create Base Model**. Each model owns independent mesh data.
3. Select the model root or any body part and adjust **Controls** in Object Mode.
4. Use the arrow beside a slider or region to reset it, or choose **Reset All Body Controls**.
5. Choose **Generate Simple Rig**, select a bone in Pose Mode, then **R** to rotate
   or **G** to translate. Use **Remove Simple Rig** to return to body editing.

Save the `.blend` file to retain shape settings. A generated rig uses native
Blender bones and modifiers and remains poseable without the plugin installed.
The rig has no IK or finger controls. Shape controls are disabled while rigged.
Renaming model objects does not change their region bindings. Changing topology,
removing rest attributes, or deleting body parts invalidates slider editing.

## Controls

| Region | Controls |
| --- | --- |
| Global | Height, torso / leg ratio, build, fullness, muscle definition |
| Head | Size |
| Shoulders | Span |
| Ribcage | Width |
| Breast | Size, gap, firmness / sag |
| Waist | Size |
| Hips | Size, outer curve |
| Butt | Size, gap, firmness / sag |
| Thigh | Length, thickness, taper |
| Leg | Length, calf / ankle size, alignment |
| Foot | Size |
| Arm | Size, length |
| Hand | Size |

Ratios are neutral at **1**; signed sculpt amounts are neutral at **0**.
Height ranges from **120–200 cm**. Breast Size ranges from **-1–2.5**,
Breast Firmness / sag from **-1.5–1**, Butt Size from **-1–2**, and Hip Size
and Thigh Thickness from **0.85–1.3**. Most other ratios range from 0.85–1.15.
The slider bounds are the authoritative limits.

Thigh and lower-leg length edits carry the torso without resizing it and update
measured Height. At the height limits, further length changes stop at the bound.
Explicit Height edits scale the complete body. Sag sculpts the rest shape; it is
not a physics simulation. The supplied stylized anatomy has separate muscle
surfaces; extreme combinations or poses can retain creases or intersections.

Materials and the packed face texture are retained. Material Preview gives a
lit view; viewport shading remains under your control.

See `NOTICES.md` for asset provenance and licensing, and `LICENSE` for the code license.
