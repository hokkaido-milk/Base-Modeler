# Joint limits and muscle weighting

This pass makes the female drawing-reference rig safer to pose and reduces
concentrated muscle deformation. It keeps 81 artist-facing controls and adds
two hidden forearm twist bones (83 bones total). All constraints and weights are
native Blender data; saved rigs do not require the add-on to keep working.

## Posing

Use **R** on joint bones. Use **G** on `root` or `core` to reposition the body.
Local joint translation and all bone scaling are locked with both channel locks
and evaluated constraints, so keyframes cannot simply detach a joint or stretch
its bone. The root remains freely rotatable for whole-character orientation.

The following are the main local rotation budgets in degrees. These are
art-directed limits relative to this model's fitted rest pose, not clinical
measurements. The arms start in a T-pose, not hanging at the sides.

| Control | Flexion/extension (X) | Axial twist (Y) | Lateral motion (Z) |
| --- | --- | --- | --- |
| Core | -30 to 90 | ±30 | ±30 |
| Pelvis adjustment | -25 to 30 | ±25 | ±20 |
| Spine | -30 to 60 | ±30 | ±35 |
| Chest | -20 to 40 | ±35 | ±25 |
| Neck | -35 to 40 | ±55 | ±30 |
| Head | -20 to 25 | ±25 | ±15 |
| Shoulder girdle | -10 to 40 (shrug) | ±15 | ±25 |
| Upper arm | -100 to 90 (lower/raise from T) | ±85 | -100 to 50, mirrored |
| Elbow / forearm | -5 to 150 | ±90 | Locked |
| Wrist | -75 to 80 | Locked | -25 to 35, mirrored |
| Hip | -30 to 135 | ±45 | -25 to 55, mirrored |
| Knee | -145 to 3 | ±8 | ±3 |
| Ankle | -50 to 30 | ±15 | ±20 |
| Toe bank | -15 to 20 | Locked | ±5 |

Positive X flexes the trunk forward. Spine and chest together reach a
100-degree forward fold, so a near-90-degree bend is available in the back
alone; core adds a bend over the hips. The pelvis also inherits 35% of core
rotation and all core translation, so a large core bend also tilts the legs;
counter-rotate the thighs to keep the feet planted. Head and
neck budgets together allow about 80 degrees of axial rotation, rather than a
180-degree turn at one neck joint. Finger knuckles allow limited spread and
extension; middle/distal joints are flexion hinges. Thumb and toe limits are
specified separately in `Base Modeler/limits.py`.

Positive local X now bends either elbow toward the front. Forearms use YZX Euler
order: Y twists along the already-bent forearm, with no singularity at a normal
90-degree elbow bend. Turn the forearm with Y rather than twisting the wrist.

## Weight changes

- Forearm skin and attached muscle shells share progressive twist weights. A
  hidden child bone cancels 75% of the forearm's axial twist proximally; its
  influence fades toward the wrist. It inherits full elbow flexion. The hand
  still receives the complete forearm rotation.
- Elbow and knee weight ramps have bounded gradients through the joint crease,
  reducing concentrated stretch/compression compared with the previous cubic
  ramp.
- Shoulder, upper-arm, pectoral, latissimus and forearm muscle weights are faired
  through each shell's own edges after transfer from the body surface. This
  reduces abrupt nearest-surface weight changes without smoothing across gaps.
- The posterior hip blend extends from 0.80 to 1.02 m in the neutral source,
  spreading seated-pose strain through the gluteal and hamstring attachment.
  The anterior hip crease retains its previous range. These source stations
  travel with shape controls; they are not fixed world positions in posed rigs.
- Weights remain nonnegative and normalized, with an exact quantized residual.
  Fingernails and toenails retain rigid distal-phalanx ownership.

For identical skeletal poses, the 99th-percentile **edge length ratio** changes
as follows (1.0 means unchanged length). These metrics describe localized mesh
strain, not biological muscle-fibre strain or whole-muscle volume.

| Pose / region | Previous | Refined |
| --- | --- | --- |
| Elbow bent 100°, triceps | 1.52 | 1.43 |
| Elbow bent 100°, forearm flexors | 1.64 | 1.52 |
| Elbow 90° plus 80° twist, triceps | 1.54 | 1.39 |
| Lowered shoulder, deltoid | 2.28 | 2.17 |
| Seated 90°, gluteus maximus | 2.06 | 1.74 |
| Seated 90°, medial hamstrings | 2.57 | 2.12 |

The comparison tool converts rotations between the old and new elbow rest axes,
so it compares equivalent poses despite the changed bone roll. Not every strain
metric improves: distributing a bend trades some local compression/stretch for
less extreme concentration elsewhere. Before/after renders and full per-region
measurements are in `artifacts/weight_refinement/`.

## Thorax, shoulder girdle and hip (binding schema 8)

- The chest pivots at 1.21 m, the thoracolumbar junction below the breasts,
  instead of mid-breast. Breasts are bound rigidly to the chest, so chest bends
  rotate them with the ribcage instead of folding them along a weight gradient.
- Lumbar and thoracic folds are stacked through the short front abdomen (navel
  down, navel up) and follow the lumbar and lower thoracic spine behind. Each
  torso transition is centred on its child joint.
- The neck is a narrow column. Previously it owned the upper chest, both
  trapezius slopes and half of each deltoid, so head turns dragged the shoulders.
  Pectoralis major carries no neck influence; trapezius and sternocleidomastoid
  weights are faired through their own edges.
- The clavicle and upper trapezius share the shoulder control, so shrugs lift
  them. The girdle/arm blend is centred on the glenohumeral joint, so lowered
  arms carry their deltoid cap instead of leaving raised shoulder pads.
- Dual-quaternion skinning remains for knees, elbows and twisting forearms. A
  second native Armature modifier (multi-modifier, `base_modeler_linear_skinning`
  group) fades the posterior pelvis/thigh zone to linear skinning. This removes
  the dual-quaternion bulge that swung the buttock into a lump below a flexed
  thigh. The anterior groin crease stays mostly dual-quaternion to limit collapse.
- The rectus femoris and vastus lateralis tips above the hip pivot keep 65% of
  the skin's pelvic share. Bound wholly to the femur, they swung back through
  the gluteus when the thigh flexed.

Edge length ratio, 99th / 1st percentile, previous binding vs schema 8:

| Pose | Region | Previous | Schema 8 |
| --- | --- | --- | --- |
| Chest forward 25° | Rectus abdominis | 1.00 / 0.37 | 1.02 / 0.50 |
| Spine 35° + chest 25° | Skin | 1.02 / 0.85 | 1.01 / 0.93 |
| Side bend | Serratus anterior | 1.50 / 0.54 | 1.04 / 0.97 |
| Side bend | External oblique | 1.31 / 0.72 | 1.47 / 0.61 |
| Torso twist | Serratus anterior | 1.39 / 0.73 | 1.05 / 0.95 |
| Neck turn 45° | Deltoid | 2.04 / 0.67 | 1.03 / 0.97 |
| Neck turn 45° | Trapezius | 1.44 / 0.77 | 1.65 / 0.53 |
| Arm lowered 80° | Deltoid | 2.29 / 0.91 | 1.92 / 0.88 |
| Arm raised 80° | Pectoralis major | 1.67 / 0.73 | 1.43 / 0.80 |
| Hip flexed 90° | Gluteus maximus | 1.74 / 0.91 | 1.44 / 0.70 |
| Hip flexed 90° | Medial hamstrings | 2.13 / 0.83 | 1.74 / 0.79 |

Side-bend and twist strain moves from the serratus/latissimus into the
obliques, and a head turn now stretches the trapezius at the neck base instead
of carrying the shoulders. `test_torso_rig.py` gates breast rigidity, deep
forward folds, neck isolation, deltoid travel, hip strain and thigh-tip travel.

## Validation and compatibility

New tests exercise 480 rotation endpoints, local translation/scale rejection,
combined head/neck yaw, elbow direction, bent-axis twist, progressive helper
weights, practical muscle strain and collapsed triangles. A separate reopen test
checks native behavior with no add-on loaded. The broader suite retains shape,
attachment, digit, joint-fit, all-control, material and persistence checks.

Native constraint matrix round-trips introduce about 1.5 micrometres of float32
rest-pose error on this mesh; absolute rest comparisons allow 3 micrometres.
This numerical tolerance is far below visible deformation. It is not a relaxation
of the face-collapse or joint-limit gates.

Existing rigs are not silently rewritten. Use the newly generated review file,
or remove and regenerate an older rig to adopt these limits and weights.
Removing a rig discards its pose. Old elbow animation needs conversion because
its local roll and Euler order have changed. Hidden deformation bones are not
intended as posing controls.

Independent rotation limits cannot guarantee that every combination is a natural
human pose. They do not model joint coupling, scapular motion, balance, muscle
contraction or body collision. Extreme combined bends can still intersect the
separate muscle shells; this pass improves the native FK approximation without
adding a collision solver or pose-specific corrective shapes.

## Anatomical references

- [CDC joint range-of-motion study](https://archive.cdc.gov/www_cdc_gov/ncbddd/jointrom/index.html): adult reference values for hip, knee, ankle, shoulder, elbow, pronation and supination. Used to inform plausible ranges, with some artistic allowance.
- [Cervical spine functional anatomy and biomechanics](https://pmc.ncbi.nlm.nih.gov/articles/PMC1250253/): cervical movement ranges and the distinction between head and neck motion. The accessible search excerpt was used; the full text was access-blocked during this review.

These references inform the chosen ranges; they do not validate this stylized
model as a medical simulator.
