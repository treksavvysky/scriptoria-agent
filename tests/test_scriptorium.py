import pathlib

import pytest

from scriptoria.scriptorium import Scriptorium, ScriptoriumError


@pytest.fixture
def scriptorium(tmp_path: pathlib.Path) -> Scriptorium:
    return Scriptorium(root=tmp_path)


def test_create_and_list_workspaces(scriptorium: Scriptorium):
    assert scriptorium.create_workspace("drafts") == {"name": "drafts", "created": True}
    assert scriptorium.create_workspace("drafts") == {"name": "drafts", "created": False}
    assert scriptorium.list_workspaces() == [{"name": "drafts", "files": 0}]


def test_invalid_workspace_name_rejected(scriptorium: Scriptorium):
    for bad in ("../escape", "UPPER", "", "sp ace", "-leading"):
        with pytest.raises(ScriptoriumError):
            scriptorium.create_workspace(bad)


def test_write_read_roundtrip(scriptorium: Scriptorium):
    scriptorium.create_workspace("drafts")
    result = scriptorium.write_file("drafts", "notes/idea.md", "# Idea\n")
    assert result["size"] == len("# Idea\n")
    assert scriptorium.read_file("drafts", "notes/idea.md") == "# Idea\n"


def test_append(scriptorium: Scriptorium):
    scriptorium.create_workspace("drafts")
    scriptorium.write_file("drafts", "log.txt", "one\n")
    scriptorium.write_file("drafts", "log.txt", "two\n", append=True)
    assert scriptorium.read_file("drafts", "log.txt") == "one\ntwo\n"


def test_path_escape_rejected(scriptorium: Scriptorium):
    scriptorium.create_workspace("drafts")
    for bad in ("../outside.txt", "/etc/passwd", "a/../../b"):
        with pytest.raises(ScriptoriumError):
            scriptorium.write_file("drafts", bad, "nope")
        with pytest.raises(ScriptoriumError):
            scriptorium.read_file("drafts", bad)


def test_move_and_delete(scriptorium: Scriptorium):
    scriptorium.create_workspace("drafts")
    scriptorium.write_file("drafts", "a.txt", "x")
    scriptorium.move_file("drafts", "a.txt", "b.txt")
    assert [f["path"] for f in scriptorium.list_files("drafts") if f["kind"] == "file"] == ["b.txt"]
    scriptorium.delete_file("drafts", "b.txt")
    assert scriptorium.list_files("drafts") == []


def test_delete_refuses_directories(scriptorium: Scriptorium):
    scriptorium.create_workspace("drafts")
    scriptorium.write_file("drafts", "sub/x.txt", "x")
    with pytest.raises(ScriptoriumError, match="directory"):
        scriptorium.delete_file("drafts", "sub")


def test_size_limit(scriptorium: Scriptorium):
    scriptorium.create_workspace("drafts")
    with pytest.raises(ScriptoriumError, match="limit"):
        scriptorium.write_file("drafts", "big.txt", "x" * (2 * 1024 * 1024 + 1))


def test_missing_workspace(scriptorium: Scriptorium):
    with pytest.raises(ScriptoriumError, match="does not exist"):
        scriptorium.list_files("ghost")
