# Base Modeler

A Blender extension for shaping an adult anime body with 27 continuous controls
and generating a native 22-bone FK rig.

The **[Base Modeler](Base%20Modeler/)** folder is the complete plugin source and
shipping folder. Zip its contents to create an installable Blender extension.
The manifest declares the official name **Base Modeler**, ID `base_modeler`,
and initial release **1.0.0**.

- [Installation and controls](Base%20Modeler/README.md)
- [Clean editable example](examples/Base%20Modeler.blend)
- [Development and build commands](docs/DEVELOPMENT.md)
- [Audit and validation](docs/AUDIT.md)
- [Code license and asset provenance](Base%20Modeler/NOTICES.md)

## Project layout

| Path | Purpose |
| --- | --- |
| `Base Modeler/` | Complete plugin: Python, native kernel source/binary and required assets |
| `examples/` | Clean editable Blender environment |
| `tests/blender/` | Blender integration and regression checks |
| `tools/` | Reproducible packaging, cleanup, validation and preview commands |
| `docs/` | Current development and audit documentation |

Build with `python3 tools/build.py`; the output is `dist/Base_Modeler.zip`.
Generated packages, local Blender profiles, validation outputs and the local
`.archive/` recovery directory are excluded from Git. No GitHub upload or
repository commit is performed by the build.
