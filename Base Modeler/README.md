# Base Modeler

Shape an adult anime body with 27 continuous controls, then generate a native
83-bone FK rig (81 controls plus two hidden twist bones) for posing. The foundation, anatomy corrections and face texture
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
   within joint limits. Use **G** on `root` or `core` to translate the body. Use **Remove Simple Rig** to return to body editing.

Save the `.blend` file to retain shape settings. A generated rig uses native
Blender bones and modifiers and remains poseable without the plugin installed.
Each hand has three bones per finger (including the thumb metacarpal). Each foot
has two bones in the big toe and three in each other toe. The `toe.L` / `toe.R`
bones move the whole toe bank. Bone collections separate the body, hands and
feet. Slender bone displays are sized to fit the skin, and nails follow their
distal phalanges as rigid plates. The rig uses direct FK posing without IK. Joint translation and bone scaling are
locked; rotation limits prevent gross over-bending. The hidden forearm twist
bones distribute rotation from the elbow toward the wrist.
Elbows flex forward with positive local X; local Y turns the forearm.
The wrist twist channel is locked because pronation/supination belongs to the forearm.
Positive local X rotation curls the digit bones toward the palm or sole.
The `core` control carries the torso and shares 35% of its rotation with the
hips; translation carries the whole body. Use `spine` and `chest` for additional
upper-body bends, and `pelvis` for a separate hip adjustment. The spine pivots
at the waist; its weight blend stays above the pelvic crest so lumbar bends
preserve the buttock origins and spread motion through the abdomen. Positive local X
on either thigh lifts the knee forward; negative local X on the shin bends the
knee. The face and chin follow the head rigidly, with blending confined to the
neck attachment. Shape controls are disabled while rigged.
Renaming model objects does not change their region bindings. Changing topology,
removing rest attributes, or deleting body parts invalidates slider editing.

After updating the plugin, existing rigs keep their saved bones and poses. To
apply the current anatomy and binding, remove and regenerate the simple rig.
Removing a rig discards its pose and returns the model to its editable shape.

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

The breast contour has a broad, rounded dome. Size grows the width, height and
projection together, with a soft transition into the chest instead of a pointed tip.
The buttocks use a rounded rear volume and softer lower corners; Size grows all
three dimensions together. The neutral neck is slightly shorter and the chin
has a broader, softer tip.

The anatomy surface pass reduces excessive relief in the shoulders, neck,
upper back, arms and anterior legs. Abdominal segments sit closer together;
the lower abdomen tapers toward the pubis and has a shallow midline groove.
The original vertex order, UVs and body attachment seams are retained.
New rigs fit and bind to this corrected neutral surface. Existing saved rigs
keep their original geometry and weights until removed and regenerated.

This remains a stylized female surface-anatomy drawing aid, not a complete
medical ecorche: the breast surface covers underlying pectoral anatomy and
several deeper muscles and tendons are not individually modeled.

Thigh and lower-leg length edits carry the torso without resizing it and update
measured Height. At the height limits, further length changes stop at the bound.
Explicit Height edits scale the complete body. Sag sculpts the rest shape; it is
not a physics simulation. The supplied stylized anatomy has separate muscle
surfaces; extreme combinations or poses can retain creases or intersections.
Strong finger and toe curls can compress small faces along the inside crease;
this rig does not include pose-specific corrective sculpting or collision handling.

Materials and the packed face texture are retained. Material Preview gives a
lit view; viewport shading remains under your control.

See `NOTICES.md` for asset provenance and licensing, and `LICENSE` for the code license.

See `../docs/WEIGHT_REVIEW.md` for joint ranges, binding changes and validation.
