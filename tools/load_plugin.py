"""Load the checkout as base_modeler for Blender-side development checks."""

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(os.environ.get("BASE_MODELER_PACKAGE", ROOT / "Base Modeler"))
spec = importlib.util.spec_from_file_location(
    "base_modeler", PACKAGE / "__init__.py", submodule_search_locations=[str(PACKAGE)]
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
