#!/usr/bin/env python3
"""Build the Claude Desktop extension (.mcpb) into this folder.

A .mcpb is a zip with manifest.json at its root. This is a uv-type bundle
(MCPB spec): Claude Desktop installs Python and the dependencies itself from
pyproject.toml and uv.lock, so the bundle carries only the source, the
manifest and its images, and the README/LICENSE that pyproject.toml names
(the host's build of the package fails without them).

The finished bundle is smoke-tested: unpacked to a temporary folder and its
server started with --help, the way Claude Desktop would start it.

    uv run python mcpb/build.py             # build and smoke-test
    uv run python mcpb/build.py --no-smoke  # build only

The post-commit hook runs it after every commit.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT_FILES = ("pyproject.toml", "uv.lock", "README.md", "LICENSE.md")
SMOKE_TIMEOUT = 300  # seconds; the first run builds a fresh environment from uv's cache


def _manifest(root: Path) -> dict:
    return json.loads((root / "mcpb" / "manifest.json").read_text(encoding="utf-8"))


def bundle_files(root: Path = REPO_ROOT) -> dict[str, Path]:
    """Map each path inside the bundle to the file it is read from.

    Source files come from git's list, so caches, build leftovers and untracked
    scratch files in src/ never ship.
    """
    manifest = _manifest(root)
    source = subprocess.run(
        ["git", "ls-files", "src"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    names = [*ROOT_FILES, manifest["icon"], *manifest.get("screenshots", []), *source]

    files = {name: root / name for name in names}
    files["manifest.json"] = root / "mcpb" / "manifest.json"
    return files


def smoke_test(bundle: Path) -> None:
    """Start the unpacked bundle's server once; raise if it does not start."""
    with tempfile.TemporaryDirectory(prefix="windows-mcp-bundle-") as unpacked:
        with zipfile.ZipFile(bundle) as archive:
            archive.extractall(unpacked)
        subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                unpacked,
                "python",
                "-m",
                "windows_mcp",
                "serve",
                "--help",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=SMOKE_TIMEOUT,
        )


def build(root: Path = REPO_ROOT, out_dir: Path | None = None, smoke: bool = True) -> Path:
    """Write windows-mcp-<version>.mcpb into out_dir (default: mcpb/) and return its path."""
    out_dir = out_dir or root / "mcpb"
    bundle = out_dir / f"windows-mcp-{_manifest(root)['version']}.mcpb"

    # Written beside the target and swapped in, so a failed build never leaves
    # a half-written bundle where the last good one was.
    partial = bundle.with_suffix(".partial")
    with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(bundle_files(root).items()):
            archive.write(path, name)
    partial.replace(bundle)

    if smoke:
        smoke_test(bundle)
    return bundle


def main(argv: list[str]) -> int:
    try:
        bundle = build(smoke="--no-smoke" not in argv)
    except subprocess.CalledProcessError as exc:
        print(f"error: {exc.cmd[0]} failed (exit {exc.returncode})", file=sys.stderr)
        print(exc.stderr or exc.stdout, file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"error: could not build the bundle: {exc}", file=sys.stderr)
        return 1

    size_kb = bundle.stat().st_size / 1024
    print(f"built {bundle.relative_to(REPO_ROOT)} ({size_kb:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
