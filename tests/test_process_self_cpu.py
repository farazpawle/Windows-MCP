"""Round-2 3.23: the server must not show itself as a runaway CPU process."""

import os
from types import SimpleNamespace

import psutil

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
