"""Every process's name, memory and CPU time from one system snapshot.

psutil reads memory per process; for the ~1/3 of processes Windows protects it falls
back to a whole-system snapshot per process, so a list of ~500 cost ~0.6 s (round-4
R4-I1). One NtQuerySystemInformation(SystemProcessInformation) call returns the same
counters for all of them in a few milliseconds.
"""

import ctypes
from ctypes import wintypes
from typing import NamedTuple

__all__ = ["ProcCounters", "read_counters"]

_SYSTEM_PROCESS_INFORMATION = 5
_STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
_EPOCH_AS_FILETIME = 116444736000000000  # 1970-01-01 in 100 ns units since 1601


class ProcCounters(NamedTuple):
    name: str
    working_set: int  # bytes, what psutil calls rss
    cpu_time: int  # user + kernel, 100 ns units
    create_time: float | None  # Unix seconds; None for Idle and System


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_void_p),
    ]


class _ProcessInfo(ctypes.Structure):
    # Leading part of SYSTEM_PROCESS_INFORMATION (winternl.h plus the fields it hides);
    # thread records follow each entry, so entries are walked by NextEntryOffset.
    _fields_ = [
        ("NextEntryOffset", wintypes.ULONG),
        ("NumberOfThreads", wintypes.ULONG),
        ("WorkingSetPrivateSize", ctypes.c_longlong),
        ("HardFaultCount", wintypes.ULONG),
        ("NumberOfThreadsHighWatermark", wintypes.ULONG),
        ("CycleTime", ctypes.c_ulonglong),
        ("CreateTime", ctypes.c_longlong),
        ("UserTime", ctypes.c_longlong),
        ("KernelTime", ctypes.c_longlong),
        ("ImageName", _UnicodeString),
        ("BasePriority", wintypes.LONG),
        ("UniqueProcessId", ctypes.c_void_p),
        ("InheritedFromUniqueProcessId", ctypes.c_void_p),
        ("HandleCount", wintypes.ULONG),
        ("SessionId", wintypes.ULONG),
        ("UniqueProcessKey", ctypes.c_size_t),
        ("PeakVirtualSize", ctypes.c_size_t),
        ("VirtualSize", ctypes.c_size_t),
        ("PageFaultCount", wintypes.ULONG),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
    ]


def _query() -> ctypes.Array:
    query = ctypes.windll.ntdll.NtQuerySystemInformation
    query.restype = ctypes.c_ulong  # NTSTATUS, unsigned so it compares with the constant
    size = 1 << 20
    needed = wintypes.ULONG()
    # Processes can start between the size probe and the read, so retry with headroom.
    for _ in range(5):
        buf = ctypes.create_string_buffer(size)
        status = query(_SYSTEM_PROCESS_INFORMATION, buf, size, ctypes.byref(needed))
        if status == 0:
            return buf
        if status != _STATUS_INFO_LENGTH_MISMATCH:
            raise OSError(f"NtQuerySystemInformation failed: 0x{status:08X}")
        size = needed.value + (64 << 10)
    raise OSError("NtQuerySystemInformation: process table kept growing")


def read_counters() -> dict[int, ProcCounters]:
    """Return {pid: ProcCounters} for every running process.

    Raises:
        OSError: when the system call fails.
    """
    buf = _query()
    base = ctypes.addressof(buf)
    counters: dict[int, ProcCounters] = {}
    offset = 0
    while True:
        entry = _ProcessInfo.from_address(base + offset)
        pid = entry.UniqueProcessId or 0
        image = entry.ImageName
        if image.Buffer:
            name = ctypes.wstring_at(image.Buffer, image.Length // 2)
        else:
            name = "System Idle Process"  # PID 0 has no image name; Task Manager's label
        created = entry.CreateTime
        counters[pid] = ProcCounters(
            name=name,
            working_set=entry.WorkingSetSize,
            cpu_time=entry.UserTime + entry.KernelTime,
            create_time=(created - _EPOCH_AS_FILETIME) / 1e7 if created else None,
        )
        if not entry.NextEntryOffset:
            return counters
        offset += entry.NextEntryOffset
