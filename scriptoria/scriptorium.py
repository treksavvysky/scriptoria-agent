"""The scriptorium — Scriptoria's drafting room.

Named, sandboxed workspaces where agents (including the custom GPT) draft
and save files without copy-paste, and where the operator gets visibility
into each agent's working files. Every file operation is jailed inside its
workspace by the salvaged FileManager engine.
"""

import re
import pathlib
from typing import Any, Dict, List, Optional

from scriptoria import config
from scriptoria.file_manager import FileManager, FileManagerError

WORKSPACE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

# Drafting-room ceiling: keeps a runaway agent from filling the disk and
# keeps responses within what a GPT action can actually carry back.
MAX_FILE_BYTES = 2 * 1024 * 1024


class ScriptoriumError(Exception):
    pass


class Scriptorium:
    def __init__(self, root: Optional[pathlib.Path] = None):
        self.root = (root or config.workspaces_root()).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _workspace_path(self, name: str) -> pathlib.Path:
        if not WORKSPACE_NAME_RE.match(name or ""):
            raise ScriptoriumError(
                f"Invalid workspace name '{name}': lowercase letters, digits, "
                "'.', '_', '-' only (must start with a letter or digit)."
            )
        return self.root / name

    def _manager(self, workspace: str) -> FileManager:
        path = self._workspace_path(workspace)
        if not path.is_dir():
            raise ScriptoriumError(f"Workspace '{workspace}' does not exist.")
        return FileManager(path)

    # -- workspaces ------------------------------------------------------

    def list_workspaces(self) -> List[Dict[str, Any]]:
        workspaces = []
        for entry in sorted(self.root.iterdir()):
            if entry.is_dir() and WORKSPACE_NAME_RE.match(entry.name):
                file_count = sum(1 for p in entry.rglob("*") if p.is_file())
                workspaces.append({"name": entry.name, "files": file_count})
        return workspaces

    def create_workspace(self, name: str) -> Dict[str, Any]:
        path = self._workspace_path(name)
        created = not path.exists()
        path.mkdir(parents=True, exist_ok=True)
        return {"name": name, "created": created}

    # -- files -----------------------------------------------------------

    def list_files(self, workspace: str, subdir: str = "") -> List[Dict[str, Any]]:
        manager = self._manager(workspace)
        try:
            entries = manager.list_dir(subdir or ".")
        except FileManagerError as e:
            raise ScriptoriumError(str(e))
        base = self._workspace_path(workspace)
        listing = []
        for entry in entries:
            path = base / entry
            listing.append({
                "path": str(entry),
                "kind": "dir" if path.is_dir() else "file",
                "size": path.stat().st_size if path.is_file() else None,
            })
        return sorted(listing, key=lambda item: (item["kind"], item["path"]))

    def read_file(self, workspace: str, path: str) -> str:
        try:
            content = self._manager(workspace).read(path)
        except FileManagerError as e:
            raise ScriptoriumError(str(e))
        if isinstance(content, bytes):
            raise ScriptoriumError(f"'{path}' is not a text file.")
        return content

    def write_file(self, workspace: str, path: str, content: str, append: bool = False) -> Dict[str, Any]:
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ScriptoriumError(
                f"Content exceeds the {MAX_FILE_BYTES // 1024} KiB drafting limit."
            )
        manager = self._manager(workspace)
        try:
            if append:
                manager.append(path, content)
            else:
                manager.write(path, content, overwrite=True)
        except FileManagerError as e:
            raise ScriptoriumError(str(e))
        size = (self._workspace_path(workspace) / path).stat().st_size
        return {"workspace": workspace, "path": path, "size": size, "appended": append}

    def move_file(self, workspace: str, source: str, destination: str) -> Dict[str, Any]:
        try:
            self._manager(workspace).move_file(source, destination)
        except FileManagerError as e:
            raise ScriptoriumError(str(e))
        return {"workspace": workspace, "moved": source, "to": destination}

    def delete_file(self, workspace: str, path: str) -> Dict[str, Any]:
        # Files only — directory deletion stays a human decision.
        manager = self._manager(workspace)
        try:
            target = manager._resolve_path(path)
        except FileManagerError as e:
            raise ScriptoriumError(str(e))
        if target.is_dir():
            raise ScriptoriumError(
                f"'{path}' is a directory; the scriptorium only deletes single files."
            )
        try:
            manager.delete(path)
        except FileManagerError as e:
            raise ScriptoriumError(str(e))
        return {"workspace": workspace, "deleted": path}
