"""Round-6 R6-6: Registry reads and writes through winreg, with the replies of the PowerShell days.

These tests use a throwaway key under HKCU\\Software\\WMCP-Test, removed after each test.
The expected replies were recorded from the PowerShell version on 2026-09-28.
"""

import os
import winreg
from unittest.mock import patch

import pytest
import pywintypes
import win32api

from windows_mcp import registry

EXECUTE_COMMAND_PATH = "windows_mcp.powershell.PowerShellExecutor.execute_command"
SUB = rf"Software\WMCP-Test\UT{os.getpid()}"
KEY = "HKCU:\\" + SUB


@pytest.fixture(autouse=True)
def scratch_key():
    yield
    try:
        win32api.RegDeleteTree(winreg.HKEY_CURRENT_USER, SUB)
    except pywintypes.error:
        pass  # the test already removed it, or never created it


def _set(name, value, reg_type="String", path=KEY):
    return registry.set_value(path, name, value, reg_type)


def _raw(name, sub=SUB):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as key:
        return winreg.QueryValueEx(key, name)


# --- a. no PowerShell -------------------------------------------------------------------


def test_no_mode_starts_powershell():
    with patch(EXECUTE_COMMAND_PATH, side_effect=AssertionError("PowerShell started")) as run:
        _set("V", "1")
        registry.get_value(KEY, "V")
        registry.list_key(KEY)
        registry.delete_entry(KEY, "V")
        registry.delete_entry(KEY)
    run.assert_not_called()


# --- b. get shows each type as before ------------------------------------------------------

TYPES = [
    ("Str", "hello wörld 'q' \"dq\"", "String", "hello wörld 'q' \"dq\""),
    ("Empty", "", "String", ""),
    ("Bin", "de,ad,be,ef", "Binary", "de,ad,be,ef"),
    ("BinEmpty", "", "Binary", ""),
    ("Dw", "0x10", "DWord", "16"),
    ("DwNeg", "-1", "DWord", "4294967295"),
    ("DwMax", "4294967295", "DWord", "4294967295"),
    ("Qw", "0xFF", "QWord", "255"),
    ("QwNeg", "-5", "QWord", "18446744073709551611"),
    ("QwMax", "18446744073709551615", "QWord", "18446744073709551615"),
    ("Multi", '["one","two <&>","ü","q\\"x"]', "MultiString", '["one","two <&>","ü","q\\"x"]'),
    ("MultiOne", "just one", "MultiString", '["just one"]'),
    ("MultiEmpty", "[]", "MultiString", "[]"),
]


@pytest.mark.parametrize(("name", "value", "reg_type", "shown"), TYPES)
def test_get_shows_each_type_as_before(name, value, reg_type, shown):
    _set(name, value, reg_type)
    assert registry.get_value(KEY, name) == f'Registry value [{KEY}] "{name}" = {shown}'


def test_get_expands_an_expandstring():
    _set("Exp", r"%TEMP%\x", "ExpandString")
    expected = os.path.expandvars(r"%TEMP%\x")
    assert registry.get_value(KEY, "Exp") == f'Registry value [{KEY}] "Exp" = {expected}'
    assert _raw("Exp") == (r"%TEMP%\x", winreg.REG_EXPAND_SZ)  # stored unexpanded


@pytest.mark.parametrize("name", ["", "(Default)", "(default)"])
def test_the_default_value_is_set_read_and_deleted(name):
    assert (
        _set(name, "defval")
        == f'Registry value [{KEY}] "(Default)" set to "defval" (type: String).'
    )
    assert registry.get_value(KEY, name) == f'Registry value [{KEY}] "(Default)" = defval'
    assert _raw("") == ("defval", winreg.REG_SZ)
    assert registry.delete_entry(KEY, "(Default)") == f'Registry value [{KEY}] "(Default)" deleted.'
    assert registry.list_key(KEY) == f"Registry key [{KEY}]:\nNo values or sub-keys found."


# --- c. set writes each type -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("reg_type", "value", "shown", "stored"),
    [
        ("String", "hi", "hi", ("hi", winreg.REG_SZ)),
        ("ExpandString", "%TEMP%", "%TEMP%", ("%TEMP%", winreg.REG_EXPAND_SZ)),
        ("Binary", "01 02 ff", "01 02 ff", (b"\x01\x02\xff", winreg.REG_BINARY)),
        ("DWord", "-1", "-1", (0xFFFFFFFF, winreg.REG_DWORD)),
        ("QWord", "0xFF", "255", (255, winreg.REG_QWORD)),
        ("MultiString", '["a","b c"]', '["a","b c"]', (["a", "b c"], winreg.REG_MULTI_SZ)),
    ],
)
def test_set_writes_each_type(reg_type, value, shown, stored):
    reply = _set("V", value, reg_type)
    assert reply == f'Registry value [{KEY}] "V" set to "{shown}" (type: {reg_type}).'
    assert _raw("V") == stored


def test_set_creates_a_missing_nested_key():
    _set("G", "g", path=KEY + r"\Child\Grand")
    assert _raw("G", SUB + r"\Child\Grand") == ("g", winreg.REG_SZ)


@pytest.mark.parametrize(
    ("reg_type", "value"),
    [("DWord", "4294967296"), ("DWord", "-2147483649"), ("QWord", "18446744073709551616")],
)
def test_a_number_too_big_for_its_type_is_refused_before_writing(reg_type, value):
    reply = _set("V", value, reg_type)
    assert reply.startswith(f"Error: invalid {reg_type} value:") and value in reply
    assert registry.list_key(KEY).startswith("Error")  # the key was not even created


# --- d. list -----------------------------------------------------------------------------------


def test_list_shows_values_then_sub_keys_with_no_carriage_return():
    _set("Str", "hello")
    _set("", "defval")
    _set("Bin", "de,ad", "Binary")
    _set("Dw", "-1", "DWord")
    _set("Multi", '["a","b"]', "MultiString")
    _set("PSName", "kept")  # PowerShell's list hid names starting with "PS"
    _set("G", "g", path=KEY + r"\Child2\Grand")
    _set("T", "t", path=KEY + r"\Child1")
    reply = registry.list_key(KEY)
    assert "\r" not in reply  # R5-2
    assert reply == (
        f"Registry key [{KEY}]:\nValues:\nStr : hello\n(default) : defval\nBin : de,ad\n"
        'Dw : 4294967295\nMulti : ["a","b"]\nPSName : kept\n\nSub-Keys:\nChild1\nChild2'
    )


def test_list_of_a_key_with_only_sub_keys():
    _set("G", "g", path=KEY + r"\Child2\Grand")
    assert registry.list_key(KEY + r"\Child2") == f"Registry key [{KEY}\\Child2]:\nSub-Keys:\nGrand"


# --- e. and f. delete ------------------------------------------------------------------------


def test_delete_keeps_the_wildcard_guard():
    _set("V", "1", path=KEY + r"\A1")
    reply = registry.delete_entry(KEY + r"\A*", recursive=True)
    assert "wildcard" in reply and reply.startswith("Error")
    assert _raw("V", SUB + r"\A1") == ("1", winreg.REG_SZ)


def test_delete_value_leaves_the_key():
    _set("V", "1")
    _set("W", "2")
    assert registry.delete_entry(KEY, "V") == f'Registry value [{KEY}] "V" deleted.'
    assert registry.list_key(KEY) == f"Registry key [{KEY}]:\nValues:\nW : 2"


def test_delete_with_an_empty_name_removes_the_default_value_not_the_key():
    # The tool says name="" is the default value; before R6-6 it deleted the whole key.
    _set("", "defval")
    _set("V", "1")
    assert registry.delete_entry(KEY, "") == f'Registry value [{KEY}] "(Default)" deleted.'
    assert registry.list_key(KEY) == f"Registry key [{KEY}]:\nValues:\nV : 1"


def test_delete_key_with_sub_keys_needs_recursive():
    _set("G", "g", path=KEY + r"\Child2\Grand")
    _set("T", "t", path=KEY + r"\Child1")
    assert registry.delete_entry(KEY) == (
        f"Error: Registry key [{KEY}] has 2 sub-key(s); nothing was deleted. "
        "Pass recursive=true to delete the key with all its sub-keys."
    )
    assert registry.delete_entry(KEY + r"\Child1") == f"Registry key [{KEY}\\Child1] deleted."
    assert registry.delete_entry(KEY, recursive=True) == f"Registry key [{KEY}] deleted."
    with pytest.raises(FileNotFoundError):
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, SUB)


@pytest.mark.parametrize("path", ["HKCU:\\", "HKCU:", "Registry::HKEY_CURRENT_USER", "HKLM\\"])
@pytest.mark.parametrize("recursive", [False, True])
def test_a_whole_hive_is_never_deleted(path, recursive):
    # Every way a key can be removed is stubbed, so this test can never delete a real hive.
    with (
        patch("win32api.RegDeleteTree") as tree,
        patch("winreg.DeleteKey") as key,
        patch(EXECUTE_COMMAND_PATH, side_effect=AssertionError("PowerShell started")) as run,
    ):
        reply = registry.delete_entry(registry.resolve_path(path), recursive=recursive)
    assert reply.startswith("Error") and "hive" in reply
    tree.assert_not_called()
    key.assert_not_called()
    run.assert_not_called()


def test_brackets_in_a_path_are_plain_characters():
    path = KEY + r"\Br[ack]et"
    _set("V", "1", path=path)
    assert registry.get_value(path, "V") == f'Registry value [{path}] "V" = 1'


# --- g. hive spellings --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spelling",
    [KEY, "HKEY_CURRENT_USER\\" + SUB, "HKCU\\" + SUB, "Registry::HKEY_CURRENT_USER\\" + SUB],
)
def test_hkcu_spellings_reach_the_same_key(spelling):
    _set("V", "same")
    path = registry.resolve_path(spelling)
    assert registry.get_value(path, "V") == f'Registry value [{path}] "V" = same'


@pytest.mark.parametrize(
    ("path", "name"),
    [
        (r"HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductName"),
        (r"HKCR:\.txt", ""),
        (r"HKU:\.DEFAULT", None),
        (r"HKCC:\System\CurrentControlSet\Control\Print\Printers", None),
    ],
)
def test_other_hives_are_read(path, name):
    path = registry.resolve_path(path)
    reply = registry.list_key(path) if name is None else registry.get_value(path, name)
    assert not reply.startswith("Error"), reply


# --- h. errors name the path and the reason --------------------------------------------------


def test_a_missing_value_names_the_path_and_the_value():
    _set("V", "1")
    assert registry.get_value(KEY, "Missing") == (
        f'Error reading registry: value "Missing" does not exist in [{KEY}].'
    )
    assert registry.delete_entry(KEY, "Missing") == (
        f'Error deleting registry value: value "Missing" does not exist in [{KEY}].'
    )


def test_a_missing_key_names_the_path():
    missing = KEY + r"\Nope"
    assert registry.get_value(missing, "X") == (
        f"Error reading registry: key [{missing}] does not exist."
    )
    assert registry.list_key(missing) == f"Error listing registry: key [{missing}] does not exist."
    assert registry.delete_entry(missing) == (
        f"Error deleting registry key: key [{missing}] does not exist."
    )
