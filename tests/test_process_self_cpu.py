"""Round-2 3.23: the server must not show itself as a runaway CPU process."""

import os
from datetime import datetime
from types import SimpleNamespace

import psutil
import pytest

from windows_mcp.process.service import list_processes


def _fake(pid: int, name: str, cpu: float, mem_mb: float = 10):
    return SimpleNamespace(
        info={
            "pid": pid,
            "name": name,
            "cpu_percent": cpu,
            "memory_info": SimpleNamespace(rss=int(mem_mb * 1024 * 1024)),
        }
    )


def test_own_process_is_marked_and_not_ranked_by_its_own_sample(monkeypatch):
    me = os.getpid()
    fakes = [_fake(me, "python.exe", 97.0), _fake(4242, "busy.exe", 12.0)]
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: fakes)

    lines = list_processes(sort_by="cpu").splitlines()

    first_row = lines[3]  # title, header, dashes, first row
    assert first_row.split()[0] == "4242"
    own = next(line for line in lines if line.split()[0] == str(me))
    assert "(this server)" in own
    assert "97" not in own


def test_cpu_is_sampled_over_a_fresh_short_window(monkeypatch):
    # Round-2 3.31: psutil's first reading per process is 0, and later ones average
    # over the whole gap since the previous list - so prime, wait, then read.
    events = []

    def fake_iter(attrs):
        events.append(("iter", tuple(attrs)))
        return [_fake(4242, "busy.exe", 12.0)]

    monkeypatch.setattr(psutil, "process_iter", fake_iter)
    monkeypatch.setattr(
        "windows_mcp.process.service.time.sleep", lambda s: events.append(("sleep", s))
    )

    list_processes(sort_by="cpu")

    assert events[0] == ("iter", ("cpu_percent",))
    assert events[1] == ("sleep", 0.5)
    assert events[2][0] == "iter" and "cpu_percent" in events[2][1]


@pytest.mark.parametrize("sort_by", ["memory", "name"])
def test_other_sorts_do_not_sample_cpu(monkeypatch, sort_by):
    # Round-3 R3-I3: the 0.5 s CPU sample made every list take ~1.6 s.
    asked = []

    def fake_iter(attrs):
        asked.append(tuple(attrs))
        return [_fake(4242, "busy.exe", 12.0)]

    monkeypatch.setattr(psutil, "process_iter", fake_iter)
    monkeypatch.setattr("windows_mcp.process.service.time.sleep", lambda s: pytest.fail("slept"))

    reply = list_processes(sort_by=sort_by)

    assert asked and all("cpu_percent" not in a for a in asked)
    assert "CPU%" not in reply and "busy.exe" in reply


def test_details_show_start_time_and_command_line_with_secrets_hidden(monkeypatch):
    # Round-3 R3-I10: tracing the Avast alert needed a separate Win32_Process query to see
    # which script a hidden powershell.exe was running.
    asked = []
    started = datetime(2026, 9, 24, 10, 5, 7).timestamp()
    tray = _fake(4242, "powershell.exe", 0.0)
    tray.info |= {
        "cmdline": ["powershell.exe", "-File", "C:\\Apps\\tray script.ps1", "-Token", "hunter22"],
        "create_time": started,
    }
    hidden = _fake(4, "System", 0.0)
    hidden.info |= {"cmdline": None, "create_time": None}  # access denied

    def fake_iter(attrs):
        asked.append(tuple(attrs))
        return [tray, hidden]

    monkeypatch.setattr(psutil, "process_iter", fake_iter)
    reply = list_processes(details=True)

    assert "cmdline" in asked[-1] and "create_time" in asked[-1]
    row = next(line for line in reply.splitlines() if line.lstrip().startswith("4242"))
    assert "2026-09-24 10:05:07" in row
    assert 'powershell.exe -File "C:\\Apps\\tray script.ps1" -Token' in row
    assert "hunter22" not in reply
    system = next(line for line in reply.splitlines() if line.lstrip().startswith("4 "))
    assert system.rstrip().endswith("-")


def test_plain_list_reads_no_command_lines(monkeypatch):
    asked = []

    def fake_iter(attrs):
        asked.append(tuple(attrs))
        return [_fake(4242, "busy.exe", 0.0)]

    monkeypatch.setattr(psutil, "process_iter", fake_iter)
    reply = list_processes()
    assert all("cmdline" not in a for a in asked) and "Command line" not in reply


def test_cpu_is_a_share_of_the_whole_machine(monkeypatch):
    # Round-2 3.32: psutil counts per core, so idle read ~1900% on 20 threads.
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [_fake(4242, "busy.exe", 400.0)])
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=True: 4)
    monkeypatch.setattr("windows_mcp.process.service.time.sleep", lambda s: None)

    row = list_processes(sort_by="cpu").splitlines()[3]

    assert "100.0%" in row
