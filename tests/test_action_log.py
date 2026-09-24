"""Round-2 C.8: opt-in action log - one readable line per tool call, secrets hidden."""

import asyncio
from pathlib import Path

import pytest

from windows_mcp.infrastructure import action_log
from windows_mcp.infrastructure.analytics import with_analytics


@pytest.fixture
def log(tmp_path):
    path = tmp_path / "actions.log"
    action_log.configure(str(path))
    yield path
    action_log.configure(None)


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


# --- redact ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "kept", "gone"),
    [
        ("New-LocalUser bob -Password hunter2 -Force", "-Password [hidden] -Force", "hunter2"),
        ("curl -H 'Authorization: Bearer abc.def-123'", "Bearer [hidden]", "abc.def-123"),
        ("set password=s3cret; go", "password=[hidden]", "s3cret"),
        ('{"api_key": "k-9x"}', '"api_key": [hidden]', "k-9x"),
        ("use sk-proj1234567890abcdef now", "use [hidden] now", "sk-proj"),
        ("token aB3dE6gH9jK2mN5pQ8sT1vW4yZ7bC0eF", "[hidden]", "aB3dE6gH9jK2mN5pQ8sT1vW4yZ7bC0eF"),
    ],
)
def test_secret_shapes_are_hidden(text, kept, gone):
    redacted = action_log.redact(text)
    assert kept in redacted and gone not in redacted


@pytest.mark.parametrize(
    "text",
    [
        r"HKLM:\SOFTWARE\Classes\CLSID\{0002DF01-0000-0000-C000-000000000046}",
        "Get-FileHash x | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "button:Save",
    ],
)
def test_ordinary_text_is_kept(text):
    assert action_log.redact(text) == text


# --- record ----------------------------------------------------------------------------


def test_off_by_default_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    action_log.configure(None)
    action_log.record("Click", {"loc": [1, 2]}, True, "ok", 0.1)
    assert list(tmp_path.iterdir()) == []


def test_one_readable_line_per_call(log):
    action_log.record(
        "Click", {"element": "button:Save", "window": None, "ctx": object()}, True, "Clicked.", 0.3
    )
    (line,) = _lines(log)
    # Layout: date and time, tool, arguments (None and ctx left out), result.
    assert line[:19].count("-") == 2 and line[10] == " "
    assert line[19:] == '  Click  element="button:Save"  -> ok 0.30s: Clicked.'


def test_secret_named_arguments_are_hidden(log):
    action_log.record("PowerShell", {"command": "ls", "auth_token": "xyz"}, True, "", 0.1)
    assert "auth_token=[hidden]" in _lines(log)[0] and "xyz" not in log.read_text()


def test_reply_is_cut_to_300_characters_on_one_line(log):
    action_log.record("FileSystem", {"mode": "read"}, True, "a\nb" + "x" * 400, 1)
    line = _lines(log)[0]
    assert "a | b" in line and line.endswith("... (403 characters)")
    assert len(line.split("-> ok 1.00s: ")[1]) < 330


def test_long_arguments_are_shortened(log):
    action_log.record("Type", {"text": "y" * 500}, True, "Typed.", 0.1)
    assert '"' + "y" * 200 + '..." (500 characters)' in _lines(log)[0]


def test_errors_are_logged(log):
    action_log.record("Registry", {"mode": "get"}, False, "Path not found", 0.05)
    assert _lines(log)[0].endswith("-> error 0.05s: Path not found")


def test_the_reply_is_redacted_too(log):
    action_log.record("PowerShell", {"command": "env"}, True, "API_KEY=abc123", 0.1)
    assert "abc123" not in log.read_text()


def test_non_text_replies_are_described(log):
    action_log.record("Screenshot", {}, True, ["Cursor at (1,2)", object()], 0.1)
    assert _lines(log)[0].endswith("-> ok 0.10s: Cursor at (1,2) [object]")


def test_calls_are_appended_in_order(log):
    for name in ("App", "Click", "Type"):
        action_log.record(name, {}, True, "", 0)
    assert [line.split()[2] for line in _lines(log)] == ["App", "Click", "Type"]


# --- the tool boundary -----------------------------------------------------------------


def test_every_wrapped_tool_call_is_logged(log):
    @with_analytics(None, "Click-Tool")
    def click(loc=None, ctx=None):
        return "Clicked."

    @with_analytics(None, "Type-Tool")
    def fail(text=None, ctx=None):
        raise ValueError("no field")

    asyncio.run(click(loc=[5, 6]))
    with pytest.raises(ValueError):
        asyncio.run(fail(text="hi"))
    first, second = _lines(log)
    assert "  Click  loc=[5, 6]  -> ok " in first and first.endswith(": Clicked.")
    assert '  Type  text="hi"  -> error ' in second and second.endswith(": no field")


def test_configure_on_uses_the_settings_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(action_log, "DEFAULT_PATH", tmp_path / "sub" / "actions.log")
    assert action_log.configure("on") == tmp_path / "sub" / "actions.log"
    action_log.record("Wait", {}, True, "", 0)
    assert (tmp_path / "sub" / "actions.log").exists()
    assert action_log.configure("off") is None


# --- serve --action-log ----------------------------------------------------------------


def _serve(monkeypatch, args, env=None):
    from click.testing import CliRunner

    import windows_mcp.__main__ as cli

    monkeypatch.setattr(cli, "discover_config_path", lambda _path: None)
    monkeypatch.setattr(cli, "_run_server", lambda **_kwargs: None)
    # Callers replace action_log.configure, so nothing is really switched on.
    return CliRunner().invoke(cli.main, ["serve", *args], env=env)


def test_serve_flag_turns_the_log_on(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(action_log, "configure", lambda v: seen.append(v) or tmp_path)
    result = _serve(monkeypatch, ["--action-log", str(tmp_path / "a.log")])
    assert result.exit_code == 0, result.output
    assert seen == [str(tmp_path / "a.log")]


def test_serve_reads_the_environment_variable(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(action_log, "configure", lambda v: seen.append(v) or None)
    result = _serve(monkeypatch, [], env={"WINDOWS_MCP_ACTION_LOG": "on"})
    assert result.exit_code == 0, result.output
    assert seen == ["on"]


@pytest.mark.parametrize(
    ("label", "name"),
    [
        ("Powershell-Tool", "PowerShell"),
        ("State-Tool", "Snapshot"),
        ("Multi-Edit-Tool", "MultiEdit"),
        ("Multi-Select-Tool", "MultiSelect"),
        ("Click-Tool", "Click"),
    ],
)
def test_the_log_uses_the_real_tool_name(log, label, name):
    # Seen live: the telemetry labels differ for four tools and must stay as they are.
    @with_analytics(None, label)
    def tool(ctx=None):
        return ""

    asyncio.run(tool())
    assert _lines(log)[0].split()[2] == name


def test_paths_keep_single_backslashes(log):
    action_log.record("Registry", {"path": r"HKCU:\Software\X", "value": 'say "hi"'}, True, "", 0)
    line = _lines(log)[0]
    assert r'path="HKCU:\Software\X"' in line and r'value="say \"hi\""' in line
