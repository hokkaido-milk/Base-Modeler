"""Build a deterministic installable ZIP from the Base Modeler folder."""

import ast
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "Base Modeler"
DIST = ROOT / "dist"


def build():
    manifest = (PACKAGE / "blender_manifest.toml").read_text()
    version = re.search(r'^version = "([^"]+)"', manifest, re.M)[1]
    assert re.search(r'^name = "Base Modeler"$', manifest, re.M)
    assert re.search(r'^id = "base_modeler"$', manifest, re.M)
    tree = ast.parse((PACKAGE / "constants.py").read_text())
    code_version = next(
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    assert version == ".".join(map(str, code_version)), "Release versions disagree"
    DIST.mkdir(exist_ok=True)
    target = DIST / "Base_Modeler.zip"
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if not path.is_file():
                continue
            if (
                "__pycache__" in path.parts
                or path.name.startswith(".")
                or path.suffix in (".pyc", ".blend1", ".blend2")
            ):
                continue
            info = zipfile.ZipInfo(
                path.relative_to(PACKAGE).as_posix(), date_time=(1980, 1, 1, 0, 0, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".zip.sha256").write_text(digest + "  " + target.name + "\n")
    print(
        f"Built {target.name} ({target.stat().st_size:,} bytes), Base Modeler {version}",
        flush=True,
    )
    return target


if __name__ == "__main__":
    build()
