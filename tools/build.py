"""Build a deterministic installable ZIP and its extension repository listing.

``dist/index.json`` is a Blender extension repository listing for the release
``v<version>`` on GitHub. Publish it as a release asset next to the ZIP: Blender's
Get Extensions and the add-on's own updater both read it from
``https://github.com/<owner>/<repo>/releases/latest/download/index.json``.
"""

import argparse
import ast
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "Base Modeler"
DIST = ROOT / "dist"
ARCHIVE = "Base_Modeler.zip"


def parse_manifest(text):
    """Parse the flat ``blender_manifest.toml`` (strings, string arrays, tables)."""
    data, table = {}, None
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.fullmatch(r"\[[A-Za-z_]+\]", line):
            table = data.setdefault(line[1:-1], {})
            continue
        match = re.fullmatch(r"([A-Za-z_]+)\s*=\s*(.+)", line)
        if not match:
            raise ValueError(f"Unsupported manifest line {number}: {line}")
        (table if table is not None else data)[match[1]] = json.loads(match[2])
    return data


def release_url(manifest, version):
    """GitHub download URL of this version's ZIP, from the manifest website."""
    match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+?)/?", manifest["website"])
    assert match, "Manifest website must be the GitHub repository URL"
    return f"https://github.com/{match[1]}/releases/download/v{version}/{ARCHIVE}"


def write_index(archive, manifest, archive_url=None, target=None):
    """Write a Blender extension repository listing (API v1) for ``archive``."""
    data = archive.read_bytes()
    entry = dict(manifest)
    entry.update(
        archive_size=len(data),
        archive_hash="sha256:" + hashlib.sha256(data).hexdigest(),
        archive_url=archive_url or release_url(manifest, manifest["version"]),
    )
    index = {"version": "v1", "blocklist": [], "data": [entry]}
    target = target or archive.with_name("index.json")
    target.write_text(json.dumps(index, indent=2) + "\n")
    return target


def write_archive(package, target, version=None, level=9):
    """Zip ``package``; ``version`` rewrites both release numbers (test builds)."""
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=level
    ) as archive:
        for path in sorted(package.rglob("*")):
            if not path.is_file():
                continue
            if (
                "__pycache__" in path.parts
                or path.name.startswith(".")
                or path.suffix in (".pyc", ".blend1", ".blend2")
            ):
                continue
            name = path.relative_to(package).as_posix()
            data = path.read_bytes()
            if version and name == "blender_manifest.toml":
                data = re.sub(
                    rb'^version = "[^"]+"',
                    f'version = "{version}"'.encode(),
                    data,
                    count=1,
                    flags=re.M,
                )
            elif version and name == "constants.py":
                numbers = ", ".join(version.split("."))
                data = re.sub(
                    rb"^VERSION = \([^)]*\)",
                    f"VERSION = ({numbers})".encode(),
                    data,
                    count=1,
                    flags=re.M,
                )
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=level)
    return target


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
    target = write_archive(PACKAGE, DIST / ARCHIVE)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".zip.sha256").write_text(digest + "  " + target.name + "\n")
    write_index(target, parse_manifest(manifest))
    print(
        f"Built {target.name} ({target.stat().st_size:,} bytes), Base Modeler {version}",
        flush=True,
    )
    return target


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()
