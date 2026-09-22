"""Regression tests for Plan/windows-mcp-open-issues.md section 1 (High)."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from windows_mcp import process, registry
from windows_mcp.filesystem.service import write_file
from windows_mcp.tools._args import as_bool
from windows_mcp.tools import filesystem as filesystem_tool_module

EXECUTE_COMMAND_PATH = "windows_mcp.powershell.PowerShellExecutor.execute_command"


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _filesystem_tool():
    mcp = FakeMCP()
    filesystem_tool_module.register(mcp, get_desktop=MagicMock(), get_analytics=lambda: None)
    tool = mcp.tools["FileSystem"]
    return lambda **kwargs: asyncio.run(tool(**kwargs))


# 1.1 FileSystem write honours overwrite=false
class TestWriteOverwrite:
    def test_refuses_existing_file_without_overwrite(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("original", encoding="utf-8")
        result = write_file(str(f), "new", overwrite=False)
        assert result.startswith("Error")
        assert f.read_text(encoding="utf-8") == "original"

    def test_overwrites_when_asked(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("original", encoding="utf-8")
        write_file(str(f), "new", overwrite=True)
        assert f.read_text(encoding="utf-8") == "new"

    def test_append_needs_no_overwrite(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("a", encoding="utf-8")
        write_file(str(f), "b", append=True)
        assert f.read_text(encoding="utf-8") == "ab"

    def test_new_file_needs_no_overwrite(self, tmp_path):
        f = tmp_path / "new.txt"
        write_file(str(f), "x")
        assert f.read_text(encoding="utf-8") == "x"

    def test_tool_passes_overwrite_through(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("original", encoding="utf-8")
        tool = _filesystem_tool()
        assert tool(mode="write", path=str(f), content="new").startswith("Error")
        tool(mode="write", path=str(f), content="new", overwrite=True)
        assert f.read_text(encoding="utf-8") == "new"


# 1.2 Booleans: yes/no accepted, unknown words rejected
class TestAsBool:
    @pytest.mark.parametrize("value", [True, "true", "TRUE", "yes", "Y", "1", "on", " On ", 1])
    def test_truthy(self, value):
        assert as_bool(value, "flag") is True

    @pytest.mark.parametrize("value", [False, "false", "no", "n", "0", "off", 0])
    def test_falsy(self, value):
        assert as_bool(value, "flag") is False

    @pytest.mark.parametrize("value", ["maybe", "", "2", None, 2.5])
    def test_unknown_rejected(self, value):
        with pytest.raises(ValueError, match="flag"):
            as_bool(value, "flag")

    def test_filesystem_recursive_yes(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "hit.txt").write_text("x", encoding="utf-8")
        result = _filesystem_tool()(mode="search", path=str(tmp_path), pattern="*.txt", recursive="yes")
        assert "hit.txt" in result

    def test_filesystem_rejects_unknown_word(self, tmp_path):
        with pytest.raises(ValueError, match="recursive"):
            _filesystem_tool()(mode="list", path=str(tmp_path), recursive="maybe")


# 1.3 Process name matching
def _fake_procs(names):
    procs = []
    for pid, name in enumerate(names, start=100):
        p = MagicMock()
        p.info = {"pid": pid, "name": name, "cpu_percent": 0.0, "memory_info": None}
        procs.append(p)
    return procs


class TestProcessNames:
    def test_list_filter_is_substring_not_fuzzy(self):
        procs = _fake_procs(["pwsh.exe", "ShellExperienceHost.exe", "notepad.exe"])
        with patch("psutil.process_iter", return_value=procs):
            result = process.list_processes(name="pwsh")
        assert "pwsh.exe" in result
        assert "ShellExperienceHost" not in result

    def test_kill_accepts_name_without_exe(self):
        procs = _fake_procs(["pwsh.exe", "pwshelper.exe"])
        with patch("psutil.process_iter", return_value=procs):
            result = process.kill_process(name="pwsh")
        procs[0].terminate.assert_called_once()
        procs[1].terminate.assert_not_called()
        assert "pwsh.exe" in result

    def test_kill_exact_with_exe(self):
        procs = _fake_procs(["PWSH.EXE", "notepad.exe"])
        with patch("psutil.process_iter", return_value=procs):
            process.kill_process(name="pwsh.exe")
        procs[0].terminate.assert_called_once()
        procs[1].terminate.assert_not_called()


# 1.4 Registry key delete refuses sub-keys unless recursive
class TestRegistryDeleteKey:
    def test_non_recursive_command_checks_subkeys(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            result = registry.delete_entry(path="HKCU:\\Software\\Test")
        cmd = mock_exec.call_args[0][0]
        assert "-Recurse" not in cmd.split("Get-ChildItem")[0]
        assert "Remove-Item" in cmd and "Get-ChildItem" in cmd
        assert "deleted" in result

    def test_refusal_reported(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("HAS_SUBKEYS:3\n", 2)):
            result = registry.delete_entry(path="HKCU:\\Software\\Test")
        assert result.startswith("Error")
        assert "3 sub-key" in result
        assert "recursive=true" in result

    def test_recursive_uses_recurse(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            registry.delete_entry(path="HKCU:\\Software\\Test", recursive=True)
        assert "-Recurse" in mock_exec.call_args[0][0]
