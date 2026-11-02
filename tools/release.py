"""Build the release assets and publish them as a GitHub release.

Without ``--publish`` this only builds and prints what it would do. Publishing
needs the GitHub CLI (``gh``) signed in with access to the repository, a clean
working tree, and the current commit pushed to ``origin``.

The release gets three assets: ``Base_Modeler.zip``, its ``.sha256`` and
``index.json``. ``index.json`` is the Blender extension repository listing that
Get Extensions and the add-on's updater read from the latest release.
"""

import argparse
import shutil
import subprocess
from pathlib import Path

from build import ARCHIVE, DIST, PACKAGE, build, parse_manifest, release_url

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish", action="store_true", help="Create the GitHub release."
    )
    parser.add_argument("--notes", help="Release notes file (default: generated).")
    args = parser.parse_args()

    archive = build()
    manifest = parse_manifest((PACKAGE / "blender_manifest.toml").read_text())
    tag = "v" + manifest["version"]
    assets = [archive, DIST / (ARCHIVE + ".sha256"), DIST / "index.json"]
    command = ["gh", "release", "create", tag]
    command += [str(path.relative_to(ROOT)) for path in assets]
    command += ["--title", f"Base Modeler {manifest['version']}", "--latest"]
    command += ["--notes-file", args.notes] if args.notes else ["--generate-notes"]

    if git("status", "--porcelain"):
        problem = "The working tree has uncommitted changes."
    elif git("tag", "--list", tag):
        problem = f"Tag {tag} already exists; bump the version first."
    else:
        head = git("rev-parse", "HEAD")
        git("fetch", "--quiet", "origin")
        pushed = git("branch", "--remotes", "--contains", head)
        problem = None if pushed else "The current commit is not pushed to origin."
        command += ["--target", head]

    print("Release:", tag)
    print("Archive URL:", release_url(manifest, manifest["version"]))
    print("Command:", " ".join(command))
    if problem:
        print("Not ready to publish:", problem)
    if not args.publish:
        print("Dry run. Pass --publish to create the release.")
        return
    if problem:
        raise SystemExit(problem)
    if not shutil.which("gh"):
        raise SystemExit("Install the GitHub CLI (gh) and run `gh auth login`.")
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
