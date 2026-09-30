"""Tests for mcpb/build.py, which packs the Claude Desktop extension.

The bundle must hold only what a uv-type bundle runs from (manifest at the
zip root, pyproject.toml, uv.lock, the source, the manifest's images, and the
README/LICENSE that pyproject.toml names). Before the build script it was
packed from the repo root and shipped plans, tests and an 82 MB index.
"""

import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    """Load mcpb/build.py, which is not an installed package."""
    path = REPO_ROOT / "mcpb" / "build.py"
    spec = importlib.util.spec_from_file_location("mcpb_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mcpb_build = _load_module()


def test_bundle_holds_only_the_runnable_files():
    names = set(mcpb_build.bundle_files(REPO_ROOT))
    manifest = json.loads((REPO_ROOT / "mcpb" / "manifest.json").read_text(encoding="utf-8"))
    tracked_source = set(
        subprocess.run(
            ["git", "ls-files", "src"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.split()
    )

    expected = {"manifest.json", "pyproject.toml", "uv.lock", "README.md", "LICENSE.md"}
    expected |= {manifest["icon"], *manifest["screenshots"]} | tracked_source
    assert names == expected


def test_build_writes_a_versioned_zip_with_the_manifest_at_its_root(tmp_path):
    bundle = mcpb_build.build(REPO_ROOT, tmp_path, smoke=False)

    version = json.loads((REPO_ROOT / "mcpb" / "manifest.json").read_text(encoding="utf-8"))[
        "version"
    ]
    assert bundle == tmp_path / f"windows-mcp-{version}.mcpb"
    with zipfile.ZipFile(bundle) as archive:
        assert json.loads(archive.read("manifest.json"))["version"] == version
        assert "src/windows_mcp/__main__.py" in archive.namelist()
