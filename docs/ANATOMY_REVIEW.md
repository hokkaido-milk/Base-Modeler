# Female surface anatomy review

The intended use is a poseable drawing reference. This pass keeps the existing
female proportions and recognizable muscle masses, but reduces the raised-plate
appearance of the surface anatomy. It is a conservative sculpt on the existing
mesh, not a replacement with a medical dissection model.

## Changes

- **Rectus abdominis:** bring the paired upper segments closer together, taper
  the oversized lower abdominal patch toward the pubis, and introduce a shallow
  midline furrow. The lower patch remains connected across its fascial bridge;
  the divisions should be read as surface landmarks, not separate organs.
- **Deltoid, infraspinatus, teres major and trapezius:** soften excessive relief
  and small surface irregularities while retaining shoulder and scapular masses.
- **External oblique and sternocleidomastoid:** reduce raised shell thickness
  for a less abrupt transition into the trunk and neck.
- **Biceps, triceps, rectus femoris, vastus lateralis and tibialis anterior:**
  modest relief reduction and volume-preserving surface fairing. Existing joint
  endpoints and limb silhouettes remain the basis of the reference.

Corrections affect 12 named regions. Most offsets are below 3.4 mm; the largest
is approximately 11.9 mm at the reshaped lower abdomen, measured in source space.
The underlying body, face and nails are unchanged. Small surface irregularities
are faired with alternating positive/negative Laplacian steps to limit shrinkage.

## Rig and mesh integrity

The 271,342 source vertices retain their order, UVs, topology and immutable rest
attributes. Anatomy offsets are compiled once, then applied before shape controls,
arm conversion and contact fitting. The new neutral surface feeds the existing
skin-section joint fitter and weight-transfer pipeline. Abdominal weights retain
the continuous lumbar field; other muscle layers inherit the skin binding.
The later weight-refinement pass adds two hidden twist bones to the 81 controls;
see `WEIGHT_REVIEW.md` for its limits and binding changes.

The native rig in the review file is freshly generated, including all vertex
weights: 26,378 vertices receive updated normalized influences. The editable example and foundation are refreshed. Existing user files
with posed rigs are deliberately preserved: remove and regenerate their rig to
adopt the new surface and binding (removal discards that rig's pose).

`test_anatomy_surface.py` compares the sculpt to the previous foundation and
checks face winding, collapsed triangles, shared seams, finite coordinates and
repeatability. The existing suite checks slider extremes, contact clearances,
normalized rig weights, hip/spine/wrist/finger poses, all 81 bone controls,
materials and save/reopen persistence. Results are in `artifacts/validation/`.

## References and interpretation

- [OpenStax: muscles of the pectoral girdle and upper limbs](https://openstax.org/books/anatomy-and-physiology-2e/pages/11-5-muscles-of-the-pectoral-girdle-and-upper-limbs)
  supplies attachment and form context for the deltoid, scapular muscles,
  pectoralis and arm groups.
- [OpenStax: pelvic girdle and lower limbs](https://openstax.org/books/anatomy-and-physiology/pages/11-6-appendicular-muscles-of-the-pelvic-girdle-and-lower-limbs)
  supplies the relationships among the gluteal, quadriceps and lower-leg groups.
- [NCBI StatPearls: anterolateral abdominal wall muscles](https://www.ncbi.nlm.nih.gov/books/NBK470334/)
  identifies rectus abdominis as paired longitudinal muscles beside the midline.
  The accessible search summary was used; the full page was access-blocked.

The amount of visible relief and smoothing is an artistic interpretation, not a
measurement derived from these references. Female superficial muscle visibility
varies with individual build and subcutaneous tissue; there is no single ideal
female definition level.

## Remaining limitations

This source is stylized and only partially represents superficial anatomy. Its
large head proportions, simplified muscle-group patches, covered pectoral region,
and missing individually modeled deep muscles/tendons remain. The sculpt does
not establish medical accuracy or add realistic muscle contraction. Separate
muscle shells can intersect in extreme combined poses; the native FK rig has no
collision solver or pose-specific corrective shapes. The model is best used for
mass, rhythm and pose studies alongside anatomical illustrations.
