"""Process list: own-process CPU (round-2 3.23), CPU sampling, details, one-read counters."""

import os
from datetime import datetime
from types import SimpleNamespace

import psutil
import pytest

from windows_mcp.process import service
from windows_mcp.process.service import list_processes
from windows_mcp.process.snapshot import ProcCounters, read_counters

SECOND = 10_000_000  # cpu_time is in 100 ns units


def _c(name: str, cpu_s: float = 0.0, mem_mb: float = 10, created: float | None = None):
    return ProcCounters(name, int(mem_mb * 1024 * 1024), int(cpu_s * SECOND), created)


def _feed(monkeypatch, *snapshots, elapsed: float = 0.5, cores: int = 1):
    """Serve the given snapshots in turn; the CPU sample window is `elapsed` seconds."""
    calls = []
    queue = list(snapshots)

    def fake_read():
        calls.append("read")
        return queue.pop(0) if len(queue) > 1 else queue[0]

    clock = iter([0.0, elapsed] * 4)
    monkeypatch.setattr(service, "read_counters", fake_read)
    monkeypatch.setattr(service.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(service.time, "sleep", lambda s: calls.append(("sleep", s)))
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=True: cores)
    return calls


def test_own_process_is_marked_and_not_ranked_by_its_own_sample(monkeypatch):
    me = os.getpid()
    _feed(
        monkeypatch,
        {me: _c("python.exe", 0), 4242: _c("busy.exe", 0)},
        {me: _c("python.exe", 0.49), 4242: _c("busy.exe", 0.06)},
    )

    lines = list_processes(sort_by="cpu").splitlines()

    first_row = lines[3]  # title, header, dashes, first row
    assert first_row.split()[0] == "4242"
    own = next(line for line in lines if line.split()[0] == str(me))
    assert "(this server)" in own
    # The CPU column itself: the real PID in the row can contain "97" (a flaky failure).
    assert own.split("(this server)")[1].split()[0] == "-"


def test_cpu_is_sampled_over_a_fresh_short_window(monkeypatch):
    # Round-2 3.31: CPU is the change in CPU time over a fresh half second.
    calls = _feed(monkeypatch, {4242: _c("busy.exe", 1.0)}, {4242: _c("busy.exe", 1.25)})

    reply = list_processes(sort_by="cpu")

    assert calls == ["read", ("sleep", 0.5), "read"]
    assert "50.0%" in reply  # 0.25 s of CPU in 0.5 s on one core


def test_system_idle_process_is_left_out_of_the_cpu_list(monkeypatch):
    # Round-4 R4-I1: idle time topped the CPU list at ~96%.
    _feed(
        monkeypatch,
        {0: _c("System Idle Process", 0), 4242: _c("busy.exe", 0)},
        {0: _c("System Idle Process", 0.48), 4242: _c("busy.exe", 0.01)},
    )

    reply = list_processes(sort_by="cpu")

    assert "System Idle Process" not in reply
    assert reply.splitlines()[3].split()[0] == "4242"


@pytest.mark.parametrize("sort_by", ["memory", "name"])
def test_other_sorts_do_not_sample_cpu(monkeypatch, sort_by):
    # Round-3 R3-I3: the 0.5 s CPU sample made every list take ~1.6 s.
    calls = _feed(monkeypatch, {4242: _c("busy.exe")})

    reply = list_processes(sort_by=sort_by)

    assert calls == ["read"]
    assert "CPU%" not in reply and "busy.exe" in reply


def test_memory_sort_is_largest_first(monkeypatch):
    _feed(monkeypatch, {1: _c("small.exe", mem_mb=5), 2: _c("big.exe", mem_mb=500)})

    rows = list_processes().splitlines()[3:]

    assert "big.exe" in rows[0] and "500.0 MB" in rows[0]


def test_details_show_start_time_and_command_line_with_secrets_hidden(monkeypatch):
    # Round-3 R3-I10: tracing the Avast alert needed a separate Win32_Process query to see
    # which script a hidden powershell.exe was running.
    started = datetime(2026, 9, 24, 10, 5, 7).timestamp()
    _feed(monkeypatch, {4242: _c("powershell.exe", created=started), 4: _c("System")})
    cmdlines = {
        4242: ["powershell.exe", "-File", "C:\\Apps\\tray script.ps1", "-Token", "hunter22"],
    }

    def fake_process(pid):
        if pid not in cmdlines:
            raise psutil.AccessDenied(pid)
        return SimpleNamespace(cmdline=lambda: cmdlines[pid])

    monkeypatch.setattr(psutil, "Process", fake_process)
    reply = list_processes(details=True)

    row = next(line for line in reply.splitlines() if line.lstrip().startswith("4242"))
    assert "2026-09-24 10:05:07" in row
    assert 'powershell.exe -File "C:\\Apps\\tray script.ps1" -Token' in row
    assert "hunter22" not in reply
    system = next(line for line in reply.splitlines() if line.lstrip().startswith("4 "))
    assert system.rstrip().endswith("-")


def test_plain_list_reads_no_command_lines(monkeypatch):
    _feed(monkeypatch, {4242: _c("busy.exe")})
    monkeypatch.setattr(psutil, "Process", lambda pid: pytest.fail("read a command line"))

    assert "Command line" not in list_processes()


def test_cpu_is_a_share_of_the_whole_machine(monkeypatch):
    # Round-2 3.32: per-core counting made idle read ~1900% on 20 threads.
    _feed(monkeypatch, {4242: _c("busy.exe", 0)}, {4242: _c("busy.exe", 2.0)}, cores=4)

    row = list_processes(sort_by="cpu").splitlines()[3]

    assert "100.0%" in row  # 2 s of CPU in 0.5 s = 4 cores busy


def test_falls_back_to_psutil_when_the_snapshot_fails(monkeypatch):
    def broken():
        raise OSError("NtQuerySystemInformation failed")

    fake = SimpleNamespace(
        info={
            "pid": 4242,
            "name": "busy.exe",
            "memory_info": SimpleNamespace(rss=20 * 1024 * 1024),
            "cpu_times": None,
            "create_time": None,
        }
    )
    monkeypatch.setattr(service, "read_counters", broken)
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [fake])

    assert "busy.exe" in list_processes() and "20.0 MB" in list_processes()


def test_real_snapshot_lists_this_process_and_system():
    # One real system read: own PID with its memory, and the protected System process
    # (PID 4) that psutil could only read through a whole snapshot of its own.
    counters = read_counters()

    me = counters[os.getpid()]
    assert me.name.lower().startswith("python") and me.working_set > 1024 * 1024
    assert me.cpu_time > 0 and me.create_time is not None
    assert counters[4].name == "System" and counters[4].working_set > 0
    assert counters[0].name == "System Idle Process"
