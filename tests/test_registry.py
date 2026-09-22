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


class TestRegistryGet:
    def test_success(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("42\n", 0)):
            result = registry.get_value(path="HKCU:\\Software\\Test", name="MyValue")
        assert "MyValue" in result
        assert "42" in result
        assert "Error" not in result

    def test_failure(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("Property not found", 1)):
            result = registry.get_value(path="HKCU:\\Software\\Test", name="Missing")
        assert "Error reading registry" in result
        assert "Property not found" in result

    def test_command_uses_ps_quote(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("val", 0)) as mock_exec:
            registry.get_value(path="HKCU:\\Software\\O'Reilly", name="key's")
        cmd = mock_exec.call_args[0][0]
        assert "HKCU:\\Software\\O''Reilly" in cmd
        assert "key''s" in cmd


class TestRegistrySet:
    def test_success(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)):
            result = registry.set_value(path="HKCU:\\Software\\Test", name="MyKey", value="hello")
        assert "set to" in result
        assert '"hello"' in result

    def test_failure(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("Access denied", 1)):
            result = registry.set_value(path="HKLM:\\Software\\Test", name="Key", value="val")
        assert "Error writing registry" in result

    def test_invalid_type(self):
        with patch(EXECUTE_COMMAND_PATH) as mock_exec:
            result = registry.set_value(
                path="HKCU:\\Test", name="Key", value="val", reg_type="Invalid"
            )
        assert "Error: invalid registry type" in result
        assert "Invalid" in result
        mock_exec.assert_not_called()

    def test_all_valid_types(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)):
            for reg_type in ("String", "ExpandString", "Binary", "DWord", "MultiString", "QWord"):
                result = registry.set_value(
                    path="HKCU:\\Test", name="K", value="01", reg_type=reg_type
                )
                assert "Error" not in result

    def test_creates_key_if_missing(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            registry.set_value(path="HKCU:\\Software\\NewKey", name="Val", value="1")
        cmd = mock_exec.call_args[0][0]
        assert "New-Item" in cmd
        assert "Test-Path" in cmd


class TestRegistryValueFormats:
    """Round-2 item 3.7: numbers, binary and multi-string replies."""

    def test_dword_empty_value_refused(self):
        with patch(EXECUTE_COMMAND_PATH) as mock_exec:
            result = registry.set_value(path="HKCU:\\Test", name="K", value="", reg_type="DWord")
        assert "Error" in result
        mock_exec.assert_not_called()

    def test_qword_empty_value_refused(self):
        with patch(EXECUTE_COMMAND_PATH) as mock_exec:
            result = registry.set_value(path="HKCU:\\Test", name="K", value="  ", reg_type="QWord")
        assert "Error" in result
        mock_exec.assert_not_called()

    def test_dword_not_a_number_refused(self):
        with patch(EXECUTE_COMMAND_PATH) as mock_exec:
            result = registry.set_value(path="HKCU:\\Test", name="K", value="abc", reg_type="DWord")
        assert "Error" in result
        mock_exec.assert_not_called()

    def test_dword_accepts_hex_prefix(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            result = registry.set_value(
                path="HKCU:\\Test", name="K", value="0x10", reg_type="DWord"
            )
        assert "Error" not in result
        cmd = mock_exec.call_args[0][0]
        assert "-Value 16 " in cmd
        assert "16" in result

    def test_dword_keeps_leading_zero_decimal(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            registry.set_value(path="HKCU:\\Test", name="K", value="01", reg_type="DWord")
        assert "-Value 1 " in mock_exec.call_args[0][0]

    def test_qword_accepts_hex_prefix(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            registry.set_value(path="HKCU:\\Test", name="K", value="0xFF", reg_type="QWord")
        assert "-Value 255 " in mock_exec.call_args[0][0]

    def test_get_returns_binary_as_hex(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("de,ad,be,ef", 0)) as mock_exec:
            result = registry.get_value(path="HKCU:\\Test", name="B")
        cmd = mock_exec.call_args[0][0]
        assert "[byte[]]" in cmd
        assert "x2" in cmd
        # -ExpandProperty unrolls the byte array and loses the type the check needs.
        assert "-ExpandProperty" not in cmd
        # Without this a missing value would come back as text, not an error.
        assert "-ErrorAction Stop" in cmd
        assert "de,ad,be,ef" in result

    def test_get_returns_multistring_as_json_list(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=('["one","two"]', 0)) as mock_exec:
            result = registry.get_value(path="HKCU:\\Test", name="M")
        assert "[string[]]" in mock_exec.call_args[0][0]
        assert '["one","two"]' in result

    def test_multistring_accepts_json_list(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            result = registry.set_value(
                path="HKCU:\\Test", name="M", value='["one", "two"]', reg_type="MultiString"
            )
        assert "Error" not in result
        assert "@('one','two')" in mock_exec.call_args[0][0]

    def test_multistring_plain_text_stays_one_item(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            registry.set_value(
                path="HKCU:\\Test", name="M", value="just one", reg_type="MultiString"
            )
        assert "@('just one')" in mock_exec.call_args[0][0]

    def test_multistring_bad_json_list_refused(self):
        with patch(EXECUTE_COMMAND_PATH) as mock_exec:
            result = registry.set_value(
                path="HKCU:\\Test", name="M", value="[1, 2]", reg_type="MultiString"
            )
        assert "Error" in result
        mock_exec.assert_not_called()


class TestRegistryDelete:
    def test_delete_value(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            result = registry.delete_entry(path="HKCU:\\Software\\Test", name="MyValue")
        assert "deleted" in result
        assert '"MyValue"' in result
        cmd = mock_exec.call_args[0][0]
        assert "Remove-ItemProperty" in cmd

    def test_delete_key(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            result = registry.delete_entry(path="HKCU:\\Software\\Test", name=None, recursive=True)
        assert "key" in result.lower()
        assert "deleted" in result
        cmd = mock_exec.call_args[0][0]
        assert "Remove-Item" in cmd
        assert "-Recurse" in cmd

    def test_delete_value_failure(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("Not found", 1)):
            result = registry.delete_entry(path="HKCU:\\Software\\Test", name="Missing")
        assert "Error deleting registry value" in result

    def test_delete_key_failure(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("Access denied", 1)):
            result = registry.delete_entry(path="HKCU:\\Software\\Protected")
        assert "Error deleting registry key" in result


class TestRegistryLiteralPath:
    """Paths must never be expanded as wildcards (round-2 bug 1.1)."""

    PATH = "HKCU:\\Software\\WMCP-Test\\Br[ack]et"

    def _commands(self, call):
        with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as mock_exec:
            call()
        return [c[0][0] for c in mock_exec.call_args_list]

    def _assert_literal(self, cmds):
        assert cmds
        for cmd in cmds:
            assert "-Path " not in cmd
            assert f"-LiteralPath {ps_quote(self.PATH)}" in cmd

    def test_get_uses_literal_path(self):
        self._assert_literal(self._commands(lambda: registry.get_value(self.PATH, "V")))

    def test_set_uses_literal_path(self):
        cmds = self._commands(lambda: registry.set_value(self.PATH, "V", "x"))
        assert "Set-ItemProperty -LiteralPath" in cmds[0]
        assert "Test-Path -LiteralPath" in cmds[0]

    def test_delete_value_uses_literal_path(self):
        self._assert_literal(self._commands(lambda: registry.delete_entry(self.PATH, "V")))

    def test_delete_key_uses_literal_path(self):
        self._assert_literal(self._commands(lambda: registry.delete_entry(self.PATH)))

    def test_delete_key_recursive_uses_literal_path(self):
        self._assert_literal(
            self._commands(lambda: registry.delete_entry(self.PATH, recursive=True))
        )

    def test_list_uses_literal_path(self):
        self._assert_literal(self._commands(lambda: registry.list_key(self.PATH)))

    def test_delete_refuses_wildcards(self):
        for path in ("HKCU:\\Software\\WMCP-Test\\A*", "HKCU:\\Software\\WMCP-Test\\B?"):
            for kwargs in ({}, {"recursive": True}, {"name": "V"}):
                with patch(EXECUTE_COMMAND_PATH) as mock_exec:
                    result = registry.delete_entry(path, **kwargs)
                assert result.startswith("Error")
                assert "wildcard" in result
                mock_exec.assert_not_called()


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


class TestRegistryList:
    def test_success(self):
        with patch(
            EXECUTE_COMMAND_PATH, return_value=("Values:\nMyKey : hello\n\nSub-Keys:\nChild1", 0)
        ):
            result = registry.list_key(path="HKCU:\\Software\\Test")
        assert "MyKey" in result
        assert "hello" in result
        assert "Child1" in result

    def test_failure(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("Path not found", 1)):
            result = registry.list_key(path="HKCU:\\Software\\Missing")
        assert "Error listing registry" in result

    def test_empty(self):
        with patch(EXECUTE_COMMAND_PATH, return_value=("No values or sub-keys found.", 0)):
            result = registry.list_key(path="HKCU:\\Software\\Empty")
        assert "No values or sub-keys found" in result
