"""Round-2 3.6: FileSystem replies say what actually happened."""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastmcp.exceptions import ToolError

from windows_mcp.filesystem.service import read_file, write_file
from windows_mcp.tools import filesystem as filesystem_tool_module


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, **kwargs):
        def decorator(func):
            self.tools[name] = func
            return func

        return decorator


def _tool():
    mcp = FakeMCP()
    filesystem_tool_module.register(mcp, get_desktop=MagicMock, get_analytics=lambda: None)
    return lambda **kwargs: asyncio.run(mcp.tools["FileSystem"](**kwargs))


# a. an append reports the bytes it added, not the whole file
class TestAppendBytes:
    def test_append_reports_the_bytes_added(self, tmp_path):
        f = tmp_path / "log.txt"
        write_file(str(f), "hello")
        reply = write_file(str(f), "!!!", append=True)
        assert "3 bytes added" in reply
        assert f.stat().st_size == 8

    def test_append_also_reports_the_new_total(self, tmp_path):
        f = tmp_path / "log.txt"
        write_file(str(f), "hello")
        assert "8 bytes total" in write_file(str(f), "!!!", append=True)

    def test_append_to_a_new_file_counts_from_zero(self, tmp_path):
        reply = write_file(str(tmp_path / "new.txt"), "abcd", append=True)
        assert "4 bytes added" in reply

    def test_a_plain_write_still_reports_the_file_size(self, tmp_path):
        reply = write_file(str(tmp_path / "new.txt"), "hello")
        assert "5 bytes" in reply and "added" not in reply


# b. the reply names the file as Windows actually saved it
def test_trailing_dot_reply_names_the_saved_file(tmp_path):
    reply = write_file(str(tmp_path / "trailingdot."), "hi")
    assert "trailingdot." not in reply
    assert "trailingdot" in reply
    assert (tmp_path / "trailingdot").exists()


# c. writing onto a folder says it is a folder
def test_write_onto_a_folder_says_it_is_a_folder(tmp_path):
    folder = tmp_path / "adir"
    folder.mkdir()
    reply = write_file(str(folder), "hi")
    assert "is a folder" in reply
    assert "Administrator" not in reply


# d. offset and limit below 1 are refused
class TestReadBounds:
    @pytest.mark.parametrize("offset", [0, -1])
    def test_offset_below_one_is_refused(self, tmp_path, offset):
        f = tmp_path / "a.txt"
        f.write_text("line1\nline2\n", encoding="utf-8")
        assert "offset must be 1 or more" in read_file(str(f), offset=offset)

    @pytest.mark.parametrize("limit", [0, -1])
    def test_limit_below_one_is_refused(self, tmp_path, limit):
        f = tmp_path / "a.txt"
        f.write_text("line1\nline2\n", encoding="utf-8")
        assert "limit must be 1 or more" in read_file(str(f), limit=limit)

    def test_valid_bounds_still_read(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("line1\nline2\nline3\n", encoding="utf-8")
        result = read_file(str(f), offset=2, limit=1)
        assert "line2" in result and "line3" not in result


# e. append and overwrite together are refused
class TestConflictingFlags:
    def test_append_with_overwrite_is_refused_without_touching_the_file(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("original", encoding="utf-8")
        reply = write_file(str(f), "new", append=True, overwrite=True)
        assert "append" in reply and "overwrite" in reply
        assert reply.startswith("Error")
        assert f.read_text(encoding="utf-8") == "original"

    def test_either_flag_alone_still_works(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x", encoding="utf-8")
        assert not write_file(str(f), "y", append=True).startswith("Error")
        assert not write_file(str(f), "z", overwrite=True).startswith("Error")


# f. an empty path is refused instead of meaning the Desktop folder
class TestEmptyPath:
    @pytest.mark.parametrize("path", ["", "   "])
    @pytest.mark.parametrize("mode", ["read", "list", "info", "delete"])
    def test_empty_path_is_refused(self, path, mode):
        # An "Error..." reply reaches the client as a tool error (round-2 2.13).
        with pytest.raises(ToolError, match="path is empty"):
            _tool()(mode=mode, path=path)

    def test_a_real_relative_path_still_works(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "platformdirs.user_desktop_dir", lambda *a, **k: str(tmp_path), raising=False
        )
        (tmp_path / "there.txt").write_text("found me", encoding="utf-8")
        assert "found me" in _tool()(mode="read", path="there.txt")
