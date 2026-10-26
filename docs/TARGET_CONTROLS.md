# Pose target balls

Generate a rig, then choose **Add Pose Targets** in the Base Modeler sidebar.
The supplied `Female Anatomy - Target Rig.blend` already has them installed.

- Select a hand or foot ball and press **G** to move the limb, or **R** to orient the hand or foot. The small tick on each ball shows its orientation. Balls sit at the hand/foot endpoint.
- Move the head ball with **G** to aim the head. Its rotation is locked; existing head limits still constrain gaze.
- Use the five named sidebar buttons to select a control. The adjacent **IK / FK** or **Look / FK** button switches that part to direct joint posing and back, snapping the controls to the current pose.
- Move **root** to move the whole rig, including targets. Move **core** to move the torso while targets stay in place relative to root.
- Fingers, toes, spine and neck retain their existing joint controls. **Alt-G / Alt-R** reset a ball toward its installation transform.

The five nondeforming control bones use Blender's native IK and tracking constraints. They do not change the mesh or its weights. Native widgets and constraints remain usable when the file is opened without the add-on; sidebar mode switching requires the add-on.

The limbs have solver joint limits and no stretching. An unreachable target can remain separated from its hand or foot. The solver balances endpoint orientation with joint limits, so some goals cannot be matched exactly. Near-straight knees use a preferred flexion bias; installation can settle knee positions by a few millimetres. Switching to FK can also settle a constrained wrist by a few millimetres. This is a posing tool, not an animation blend system or a collision solver: check body intersections and extreme combined poses visually. Use FK when a particular bend needs manual adjustment.
