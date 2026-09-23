"""Round-2 3.25: a key's (Default) value can be set, read and deleted."""

from unittest.mock import patch

import pytest

from windows_mcp import registry

EXECUTE_COMMAND_PATH = "windows_mcp.powershell.PowerShellExecutor.execute_command"


@pytest.mark.parametrize("name", ["", "(Default)", "(default)"])
def test_set_writes_the_default_value(name):
    with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as run:
        reply = registry.set_value(path="HKCU:\\Software\\T", name=name, value="hi")
    # PowerShell refuses -Name '' but maps '(default)' to the unnamed value.
    assert "-Name '(default)'" in run.call_args[0][0]
    assert '"(Default)" set to "hi"' in reply


@pytest.mark.parametrize("name", ["", "(DEFAULT)"])
def test_get_reads_the_default_value(name):
    with patch(EXECUTE_COMMAND_PATH, return_value=("hi\n", 0)) as run:
        reply = registry.get_value(path="HKCU:\\Software\\T", name=name)
    command = run.call_args[0][0]
    assert "-Name '(default)'" in command
    assert ".'(default)'" in command
    assert reply == 'Registry value [HKCU:\\Software\\T] "(Default)" = hi'


def test_delete_default_value_does_not_remove_the_key():
    with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as run:
        reply = registry.delete_entry(path="HKCU:\\Software\\T", name="(Default)")
    command = run.call_args[0][0]
    # Remove-ItemProperty cannot delete '(default)'; the .NET key can.
    assert "DeleteValue('')" in command
    assert "Remove-Item " not in command
    assert reply == 'Registry value [HKCU:\\Software\\T] "(Default)" deleted.'


def test_an_ordinary_name_is_unchanged():
    with patch(EXECUTE_COMMAND_PATH, return_value=("", 0)) as run:
        registry.set_value(path="HKCU:\\Software\\T", name="Color", value="red")
    assert "-Name 'Color'" in run.call_args[0][0]
