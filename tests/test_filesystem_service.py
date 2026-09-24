import pytest

from windows_mcp.filesystem.service import (
    read_file,
    write_file,
    copy_path,
    move_path,
    delete_path,
    list_directory,
    search_files,
    get_file_info,
)


class TestReadFile:
    def test_read_entire_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world", encoding="utf-8")
        result = read_file(str(f))
        assert "hello world" in result

    def test_read_with_offset_and_limit(self, tmp_path):
        f = tmp_path / "lines.txt"
        f.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")
        result = read_file(str(f), offset=2, limit=2)
        assert "line2" in result
        assert "line3" in result
        assert "line4" not in result

    def test_read_nonexistent(self, tmp_path):
        result = read_file(str(tmp_path / "nope.txt"))
        assert "Error: File not found" in result

    def test_read_directory_path(self, tmp_path):
        result = read_file(str(tmp_path))
        assert "Error: Path is not a file" in result


class TestReadLargeFile:
    """Round-2 2.9: offset/limit read part of a file over the size cap."""

    @pytest.fixture
    def big(self, tmp_path, monkeypatch):
        monkeypatch.setattr("windows_mcp.filesystem.service.MAX_READ_SIZE", 100)
        f = tmp_path / "big.log"
        f.write_text("".join(f"line{i}\n" for i in range(1, 51)), encoding="utf-8")
        return f

    def test_offset_and_limit_read_the_requested_lines(self, big):
        result = read_file(str(big), offset=1, limit=2)
        assert result.endswith("Lines 1-2 of 50:\nline1\nline2\n")

    def test_whole_file_refusal_names_the_powershell_tool(self, big):
        result = read_file(str(big))
        assert result.startswith("Error: File too large")
        assert "PowerShell tool" in result and "Shell tool" not in result.replace("PowerShell", "")

    def test_offset_to_end_over_the_cap_is_refused(self, big):
        assert read_file(str(big), offset=2).startswith("Error: File too large")


class TestWriteFile:
    def test_write_new_file(self, tmp_path):
        f = tmp_path / "out.txt"
        result = write_file(str(f), "content")
        assert "Written to" in result
        assert f.read_text(encoding="utf-8") == "content"

    def test_append_to_file(self, tmp_path):
        f = tmp_path / "out.txt"
        f.write_text("first", encoding="utf-8")
        write_file(str(f), " second", append=True)
        assert f.read_text(encoding="utf-8") == "first second"

    def test_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "a" / "b" / "c.txt"
        result = write_file(str(f), "deep")
        assert "Written to" in result
        assert f.read_text(encoding="utf-8") == "deep"


class TestCopyPath:
    def test_copy_file(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("data", encoding="utf-8")
        dst = tmp_path / "dst.txt"
        result = copy_path(str(src), str(dst))
        assert "Copied file" in result
        assert dst.read_text(encoding="utf-8") == "data"

    def test_copy_directory(self, tmp_path):
        src = tmp_path / "srcdir"
        src.mkdir()
        (src / "file.txt").write_text("inside", encoding="utf-8")
        dst = tmp_path / "dstdir"
        result = copy_path(str(src), str(dst))
        assert "Copied directory" in result
        assert (dst / "file.txt").read_text(encoding="utf-8") == "inside"

    def test_copy_source_not_found(self, tmp_path):
        result = copy_path(str(tmp_path / "nope"), str(tmp_path / "dst"))
        assert "Error: Source not found" in result

    def test_copy_destination_exists_no_overwrite(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("data", encoding="utf-8")
        dst = tmp_path / "dst.txt"
        dst.write_text("existing", encoding="utf-8")
        result = copy_path(str(src), str(dst))
        assert "Error: Destination already exists" in result

    def test_copy_destination_exists_overwrite(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("new", encoding="utf-8")
        dst = tmp_path / "dst.txt"
        dst.write_text("old", encoding="utf-8")
        result = copy_path(str(src), str(dst), overwrite=True)
        assert "Copied file" in result
        assert dst.read_text(encoding="utf-8") == "new"


class TestMovePath:
    def test_move_file(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("data", encoding="utf-8")
        dst = tmp_path / "dst.txt"
        result = move_path(str(src), str(dst))
        assert "Moved" in result
        assert not src.exists()
        assert dst.read_text(encoding="utf-8") == "data"

    def test_move_source_not_found(self, tmp_path):
        result = move_path(str(tmp_path / "nope"), str(tmp_path / "dst"))
        assert "Error: Source not found" in result

    def test_move_destination_exists_no_overwrite(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("data", encoding="utf-8")
        dst = tmp_path / "dst.txt"
        dst.write_text("existing", encoding="utf-8")
        result = move_path(str(src), str(dst))
        assert "Error: Destination already exists" in result


class TestDeletePath:
    def test_delete_file(self, tmp_path):
        f = tmp_path / "del.txt"
        f.write_text("bye", encoding="utf-8")
        result = delete_path(str(f))
        assert "Deleted file" in result
        assert not f.exists()

    def test_delete_empty_dir(self, tmp_path):
        d = tmp_path / "emptydir"
        d.mkdir()
        result = delete_path(str(d))
        assert "Deleted directory" in result
        assert not d.exists()

    def test_delete_nonempty_dir_without_recursive(self, tmp_path):
        d = tmp_path / "fulldir"
        d.mkdir()
        (d / "file.txt").write_text("x", encoding="utf-8")
        result = delete_path(str(d), recursive=False)
        assert "Error: Directory is not empty" in result
        assert d.exists()

    def test_delete_nonempty_dir_recursive(self, tmp_path):
        d = tmp_path / "fulldir"
        d.mkdir()
        (d / "file.txt").write_text("x", encoding="utf-8")
        result = delete_path(str(d), recursive=True)
        assert "Deleted directory" in result
        assert not d.exists()

    def test_delete_not_found(self, tmp_path):
        result = delete_path(str(tmp_path / "ghost"))
        assert "Error: Path not found" in result


class TestListDirectory:
    def test_list_basic(self, tmp_path):
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        result = list_directory(str(tmp_path))
        assert "a.txt" in result
        assert "b.txt" in result

    def test_list_with_pattern(self, tmp_path):
        (tmp_path / "hello.py").write_text("x", encoding="utf-8")
        (tmp_path / "hello.txt").write_text("x", encoding="utf-8")
        result = list_directory(str(tmp_path), pattern="*.py")
        assert "hello.py" in result
        assert "hello.txt" not in result

    def test_list_hides_hidden_by_default(self, tmp_path):
        (tmp_path / ".hidden").write_text("x", encoding="utf-8")
        (tmp_path / "visible").write_text("x", encoding="utf-8")
        result = list_directory(str(tmp_path))
        assert ".hidden" not in result
        assert "visible" in result

    def test_list_shows_hidden_when_enabled(self, tmp_path):
        (tmp_path / ".hidden").write_text("x", encoding="utf-8")
        result = list_directory(str(tmp_path), show_hidden=True)
        assert ".hidden" in result

    def test_list_empty(self, tmp_path):
        result = list_directory(str(tmp_path))
        assert "empty" in result.lower()

    def test_list_not_found(self, tmp_path):
        result = list_directory(str(tmp_path / "nope"))
        assert "Error: Directory not found" in result

    def test_dirs_listed_before_files(self, tmp_path):
        (tmp_path / "z_file.txt").write_text("x", encoding="utf-8")
        (tmp_path / "a_dir").mkdir()
        result = list_directory(str(tmp_path))
        dir_pos = result.index("a_dir")
        file_pos = result.index("z_file.txt")
        assert dir_pos < file_pos


class TestSearchFiles:
    def test_search_basic(self, tmp_path):
        (tmp_path / "a.py").write_text("x", encoding="utf-8")
        (tmp_path / "b.txt").write_text("x", encoding="utf-8")
        result = search_files(str(tmp_path), "*.py")
        assert "a.py" in result
        assert "b.txt" not in result

    def test_search_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("x", encoding="utf-8")
        result = search_files(str(tmp_path), "*.py", recursive=True)
        assert "deep.py" in result

    def test_search_no_matches(self, tmp_path):
        result = search_files(str(tmp_path), "*.xyz")
        assert "No matches found" in result

    def test_search_path_not_found(self, tmp_path):
        result = search_files(str(tmp_path / "nope"), "*.py")
        assert "Error: Search path not found" in result


class TestGetFileInfo:
    def test_file_info(self, tmp_path):
        f = tmp_path / "info.txt"
        f.write_text("hello", encoding="utf-8")
        result = get_file_info(str(f))
        assert "Type: File" in result
        assert "Extension: .txt" in result
        assert "5" in result  # 5 bytes

    def test_dir_info(self, tmp_path):
        d = tmp_path / "mydir"
        d.mkdir()
        (d / "child.txt").write_text("x", encoding="utf-8")
        result = get_file_info(str(d))
        assert "Type: Directory" in result
        assert "1 files" in result

    def test_not_found(self, tmp_path):
        result = get_file_info(str(tmp_path / "nope"))
        assert "Error: Path not found" in result

    def test_dir_size_is_the_total_of_its_files(self, tmp_path):
        # R3-8: a folder reported its own entry size (4 KB), not what it holds.
        (tmp_path / "a.txt").write_bytes(b"x" * 400)
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_bytes(b"y" * 7)
        result = get_file_info(str(tmp_path))
        assert "(407 bytes)" in result
        assert "subfolders included" in result

    def test_dir_size_walk_is_capped(self, tmp_path, monkeypatch):
        monkeypatch.setattr("windows_mcp.filesystem.service.MAX_SIZE_WALK", 2)
        for name in "abc":
            (tmp_path / f"{name}.txt").write_bytes(b"z")
        result = get_file_info(str(tmp_path))
        assert "first 2 files" in result
