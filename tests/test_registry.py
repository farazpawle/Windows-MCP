import asyncio
from unittest.mock import patch

import pytest
from fastmcp.exceptions import ToolError

from windows_mcp import registry
from windows_mcp.powershell.utils import ps_quote


EXECUTE_COMMAND_PATH = "windows_mcp.powershell.PowerShellExecutor.execute_command"


class TestPsQuote:
    def test_simple_string(self):
        assert ps_quote("hello") == "'hello'"

    def test_single_quote_escaping(self):
        assert ps_quote("it's") == "'it''s'"

    def test_double_quotes_not_escaped(self):
        assert ps_quote('say "hi"') == """'say "hi"'"""

    def test_dollar_sign_not_expanded(self):
        assert ps_quote("$env:PATH") == "'$env:PATH'"

    def test_empty_string(self):
        assert ps_quote("") == "''"

    def test_registry_path(self):
        result = ps_quote("HKCU:\\Software\\Test")
        assert result == "'HKCU:\\Software\\Test'"


class TestRegistryRefusesBadValuesBeforeWriting:
    """Round-2 item 3.7: a bad type or number is refused before anything is written."""

    @pytest.mark.parametrize(
        ("value", "reg_type"),
        [
            ("val", "Invalid"),
            ("", "DWord"),
            ("  ", "QWord"),
            ("abc", "DWord"),
            ("[1, 2]", "MultiString"),
        ],
    )
    def test_refused(self, value, reg_type):
        with patch("winreg.CreateKeyEx") as create:
            result = registry.set_value(
                path=r"HKCU:\Test", name="K", value=value, reg_type=reg_type
            )
        assert result.startswith("Error")
        create.assert_not_called()


class TestResolvePath:
    """Only registry paths may reach PowerShell (round-2 bug 1.2)."""

    def test_drive_paths_unchanged(self):
        for path in ("HKCU:\\Software", "hkcu:\\Software\\X", "HKLM:\\SOFTWARE", "HKCU:\\"):
            assert registry.resolve_path(path) == path

    def test_other_hives_become_provider_paths(self):
        assert registry.resolve_path("HKCR:\\.txt") == "Registry::HKEY_CLASSES_ROOT\\.txt"
        assert registry.resolve_path("HKU:\\.DEFAULT") == "Registry::HKEY_USERS\\.DEFAULT"
        assert registry.resolve_path("hkcc:\\Software") == "Registry::HKEY_CURRENT_CONFIG\\Software"

    def test_regedit_style_names(self):
        assert registry.resolve_path("HKLM\\X") == "Registry::HKEY_LOCAL_MACHINE\\X"
        assert (
            registry.resolve_path("HKEY_CURRENT_USER\\Software")
            == "Registry::HKEY_CURRENT_USER\\Software"
        )
        assert registry.resolve_path("HKCU") == "Registry::HKEY_CURRENT_USER"

    def test_provider_paths(self):
        path = "Registry::HKEY_CURRENT_USER\\Software"
        assert registry.resolve_path(path) == path
        assert (
            registry.resolve_path("registry::hkey_local_machine\\SOFTWARE")
            == "Registry::HKEY_LOCAL_MACHINE\\SOFTWARE"
        )

    def test_non_registry_paths_refused(self):
        for path in (
            "",
            " ",
            "Software\\MyApp",
            "C:\\Temp",
            "%TEMP%\\x",
            "..\\x",
            "\\\\server\\share",
            "HKCUX\\Software",
            "HKXX:\\Software",
            "Registry::C:\\Temp",
            "Registry::",
        ):
            try:
                registry.resolve_path(path)
            except ValueError as e:
                assert "not a registry path" in str(e)
            else:
                raise AssertionError(f"{path!r} was accepted")


class TestRegistryToolRefusesNonRegistryPaths:
    def test_tool_refuses_before_powershell(self):
        from fastmcp import FastMCP

        from windows_mcp.tools.registry import register

        mcp = FastMCP("t")
        register(mcp, get_desktop=lambda: None, get_analytics=lambda: None)
        for mode, extra in (
            ("list", {}),
            ("get", {"name": "V"}),
            ("set", {"name": "V", "value": "1"}),
            ("delete", {"recursive": True}),
        ):
            with patch(EXECUTE_COMMAND_PATH) as mock_exec:
                with pytest.raises(ToolError, match="not a registry path"):  # 2.13: tool error
                    asyncio.run(
                        mcp.call_tool("Registry", {"mode": mode, "path": "C:\\Temp\\x", **extra})
                    )
            mock_exec.assert_not_called()
