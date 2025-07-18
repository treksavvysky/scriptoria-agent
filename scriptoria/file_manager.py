class FileManagerError(Exception):
  """Custom exception for file manager operations."""
  pass


import logging
import os
import pathlib
import shutil
import tempfile
import threading
from typing import Callable


class FileManager:
  """Manages file operations within a specified workspace."""

  def __init__(
      self,
      workspace_root: pathlib.Path,
      logger: logging.Logger | None = None,
      post_write_hooks: list[Callable[[pathlib.Path], None]] | None = None, # Restoring this
  ):
    """
    Initializes the FileManager.

    Args:
      workspace_root: The root directory for all file operations.
      logger: Optional logger instance. If None, a default logger is created.
      post_write_hooks: Optional list of functions to call after a file is written.
    """
    self.workspace_root = workspace_root.resolve()
    self.lock = threading.Lock()
    self.logger = logger or logging.getLogger(__name__)
    # Note: Application should configure logging. FileManager does not call basicConfig.
    self.post_write_hooks = post_write_hooks or [] # Restoring original attribute


  def _resolve_path(self, rel_path: str | pathlib.Path) -> pathlib.Path:
    """
    Resolves a relative path within the workspace.

    Ensures the path is relative, does not contain '..' components,
    and resolves to a location within the workspace_root.

    Args:
      rel_path: The relative path (string or Path object) to resolve.

    Returns:
      The resolved absolute pathlib.Path object.

    Raises:
      FileManagerError: If the path is absolute, contains '..',
                        or resolves outside the workspace_root.
    """
    self.logger.debug(f"Attempting to resolve path: {rel_path}")
    if not isinstance(rel_path, pathlib.Path):
      rel_path = pathlib.Path(rel_path)

    if rel_path.is_absolute() or ".." in rel_path.parts:
      msg = f"Path must be relative and not contain '..': {rel_path}"
      self.logger.error(msg)
      raise FileManagerError(msg)

    abs_path = (self.workspace_root / rel_path).resolve()

    # Check if the resolved path is within the workspace root.
    # This covers cases like symlinks pointing outside.
    if self.workspace_root != abs_path and self.workspace_root not in abs_path.parents:
      msg = f"Resolved path is outside the workspace: {abs_path}"
      self.logger.error(msg)
      raise FileManagerError(msg)
    self.logger.debug(f"Resolved path {rel_path} to {abs_path}")
    return abs_path

  def read(self, rel_path: str | pathlib.Path, *, mode: str = "r") -> str | bytes:
    """
    Reads content from a file in the workspace.

    Args:
      rel_path: The relative path (string or Path object) to the file.
      mode: The mode to open the file in (e.g., 'r', 'rb'). Defaults to 'r'.

    Returns:
      The file content as a string or bytes, depending on the mode.

    Raises:
      FileManagerError: If the path is invalid, does not point to a file,
                        or if reading fails due to an IOError or UnicodeDecodeError.
    """
    self.logger.debug(f"Attempting to read file: {rel_path} with mode '{mode}'")
    abs_path = self._resolve_path(rel_path)
    with self.lock:
      if not abs_path.exists():
        msg = f"File not found: {abs_path}"
        self.logger.error(msg)
        raise FileManagerError(msg)
      if not abs_path.is_file():
        msg = f"Path is not a file: {abs_path}"
        self.logger.error(msg)
        raise FileManagerError(msg)
      try:
        with open(abs_path, mode) as f:
          content = f.read()
        self.logger.info(f"Successfully read file: {abs_path} (mode: '{mode}')")
        return content
      except (IOError, UnicodeDecodeError) as e:
        msg = f"Error reading file {abs_path} (mode: '{mode}'): {e}"
        self.logger.error(msg)
        raise FileManagerError(msg)

  def write(
      self,
      rel_path: str | pathlib.Path,
      content: str | bytes,
      *,
      overwrite: bool = False,
      binary: bool = False,
  ) -> None:
    """
    Writes content to a file in the workspace.

    This method writes atomically by first writing to a temporary file
    in the same directory and then replacing the target file.

    Args:
      rel_path: The relative path (string or Path object) to the file.
      content: The content to write (string or bytes).
      overwrite: If True, overwrite the file if it exists. Defaults to False.
      binary: If True, write in binary mode ('wb'). Otherwise, text mode ('w').
              Defaults to False.

    Raises:
      FileManagerError: If the path is invalid, if the file exists and
                        overwrite is False, if content type mismatches binary flag,
                        or if any IO operation fails.
    """
    self.logger.debug(
        f"Attempting to write to file: {rel_path} (overwrite: {overwrite}, binary: {binary})"
    )
    abs_path = self._resolve_path(rel_path)
    write_mode = "wb" if binary else "w"

    if binary and not isinstance(content, bytes):
      msg = "Binary mode set to True, but content is not bytes."
      self.logger.error(f"{msg} Path: {abs_path}")
      raise FileManagerError(msg)
    if not binary and not isinstance(content, str):
      msg = "Binary mode set to False, but content is not string."
      self.logger.error(f"{msg} Path: {abs_path}")
      raise FileManagerError(msg)

    with self.lock:
      if abs_path.exists():
        if not abs_path.is_file():
            msg = f"Cannot write: Path exists but is not a file: {abs_path}"
            self.logger.error(msg)
            raise FileManagerError(msg)
        if not overwrite:
          msg = f"File exists and overwrite is False: {abs_path}"
          self.logger.error(msg)
          raise FileManagerError(msg)

      # Ensure parent directory exists using the internal helper for consistency
      # self.ensure_dir(abs_path.parent.relative_to(self.workspace_root), exist_ok=True)
      # The above would re-acquire lock. Simpler to just mkdir here as it was.
      abs_path.parent.mkdir(parents=True, exist_ok=True)

      temp_file_path = None # Initialize for finally block
      try:
        # Create a temporary file in the same directory
        with tempfile.NamedTemporaryFile(
            mode=write_mode, delete=False, dir=abs_path.parent.as_posix()
        ) as tmp_file:
          tmp_file.write(content)
          temp_file_path = tmp_file.name

        os.replace(temp_file_path, abs_path.as_posix())
        self.logger.info(
            f"Successfully wrote file: {abs_path} (overwrite: {overwrite}, binary: {binary})"
        )

        # Call post-write hooks
        for hook in self.post_write_hooks:
          hook_name_for_log = getattr(hook, 'name', str(hook))
          try:
            self.logger.debug(f"Calling post-write hook {hook_name_for_log} for {abs_path}")
            hook(abs_path)
          except Exception as e:
            self.logger.error(
                f"Post-write hook {hook_name_for_log} failed for {abs_path}: {e}"
            )
      except IOError as e:
        msg = f"Error writing file {abs_path}: {e}"
        self.logger.error(msg)
        raise FileManagerError(msg)
      finally:
        if temp_file_path and os.path.exists(temp_file_path):
          try:
            os.unlink(temp_file_path)
            self.logger.debug(f"Successfully deleted temporary file: {temp_file_path}")
          except OSError as e:
            self.logger.error(f"Error deleting temporary file {temp_file_path}: {e}")

  def append(
      self, rel_path: str | pathlib.Path, content: str | bytes, *, binary: bool = False
  ) -> None:
    """
    Appends content to a file in the workspace.

    If the file does not exist, it is created. Parent directories are also
    created if they don't exist.

    Args:
      rel_path: The relative path (string or Path object) to the file.
      content: The content to append (string or bytes).
      binary: If True, append in binary mode ('ab'). Otherwise, text mode ('a').
              Defaults to False.

    Raises:
      FileManagerError: If the path is invalid, content type mismatches binary flag,
                        or if any IO operation fails.
    """
    self.logger.debug(
        f"Attempting to append to file: {rel_path} (binary: {binary})"
    )
    abs_path = self._resolve_path(rel_path)
    append_mode = "ab" if binary else "a"

    if binary and not isinstance(content, bytes):
      msg = "Binary mode set to True, but content for append is not bytes."
      self.logger.error(f"{msg} Path: {abs_path}")
      raise FileManagerError(msg)
    if not binary and not isinstance(content, str):
      msg = "Binary mode set to False, but content for append is not string."
      self.logger.error(f"{msg} Path: {abs_path}")
      raise FileManagerError(msg)

    with self.lock:
      # Ensure parent directory exists
      # self.ensure_dir(abs_path.parent.relative_to(self.workspace_root), exist_ok=True)
      # The above would re-acquire lock. Simpler to just mkdir here as it was.
      abs_path.parent.mkdir(parents=True, exist_ok=True)

      if abs_path.exists() and not abs_path.is_file():
          msg = f"Cannot append: Path exists but is not a file: {abs_path}"
          self.logger.error(msg)
          raise FileManagerError(msg)

      try:
        with open(abs_path, append_mode) as f:
          f.write(content)
        self.logger.info(
            f"Successfully appended to file: {abs_path} (binary: {binary})"
        )
        # Call post-write hooks
        for hook in self.post_write_hooks:
          hook_name_for_log = getattr(hook, 'name', str(hook))
          try:
            self.logger.debug(f"Calling post-append hook {hook_name_for_log} for {abs_path}")
            hook(abs_path)
          except Exception as e:
            self.logger.error(
                f"Post-append hook {hook_name_for_log} failed for {abs_path}: {e}"
            )
      except IOError as e:
        msg = f"Error appending to file {abs_path}: {e}"
        self.logger.error(msg)
        raise FileManagerError(msg)

  def delete(self, rel_path: str | pathlib.Path, *, recursive: bool = False) -> None:
    """Deletes a file or directory in the workspace.

    Args:
      rel_path: The relative path (string or Path object) to the file or directory.
      recursive: If True, delete directories recursively. Defaults to False.
                 This must be True to delete a non-empty directory.

    Raises:
      FileManagerError: If the path is invalid, or if deletion fails (e.g.,
                        trying to delete a non-empty directory with recursive=False).
    """
    self.logger.debug(
        f"Attempting to delete path: {rel_path} (recursive: {recursive})"
    )
    abs_path = self._resolve_path(rel_path)
    with self.lock:
      if not abs_path.exists():
        self.logger.warning(
            f"Attempted to delete non-existent path: {abs_path}. Operation skipped."
        )
        return

      try:
        if abs_path.is_file():
          abs_path.unlink()
          self.logger.info(f"Successfully deleted file: {abs_path}")
        elif abs_path.is_dir():
          if recursive:
            shutil.rmtree(abs_path)
            self.logger.info(
                f"Successfully deleted directory recursively: {abs_path}"
            )
          else:
            # Check if directory is empty before attempting rmdir
            if any(abs_path.iterdir()):
              msg = (
                  f"Directory {abs_path} is not empty and recursive flag is False."
              )
              self.logger.error(msg)
              raise FileManagerError(msg)
            abs_path.rmdir()
            self.logger.info(f"Successfully deleted empty directory: {abs_path}")
        else:
            # Path exists but is neither a file nor a directory (e.g. broken symlink)
            # Try to unlink it, similar to how a file would be handled.
            abs_path.unlink()
            self.logger.info(f"Successfully deleted special file (e.g. symlink): {abs_path}")

      except (IOError, OSError) as e:
        msg = f"Error deleting path {abs_path}: {e}"
        self.logger.error(msg)
        raise FileManagerError(msg)

  def list_dir(
      self, rel_dir: str | pathlib.Path = ".", pattern: str = "*"
  ) -> list[pathlib.Path]:
    """
    Lists the contents of a directory in the workspace.

    Args:
      rel_dir: The relative path (string or Path object) to the directory.
               Defaults to the workspace root ('.').
      pattern: The glob pattern to match files and directories within rel_dir.
               Defaults to '*' (match all).

    Returns:
      A list of pathlib.Path objects, each relative to the workspace_root.

    Raises:
      FileManagerError: If rel_dir is invalid, does not exist, or is not a directory,
                        or if listing fails for other reasons.
    """
    self.logger.debug(
        f"Attempting to list directory: {rel_dir} with pattern '{pattern}'"
    )
    abs_dir_path = self._resolve_path(rel_dir)
    with self.lock:
      if not abs_dir_path.exists():
        msg = f"Directory not found: {abs_dir_path}"
        self.logger.error(msg)
        raise FileManagerError(msg)
      if not abs_dir_path.is_dir():
        msg = f"Path is not a directory: {abs_dir_path}"
        self.logger.error(msg)
        raise FileManagerError(msg)
      try:
        relative_paths = [
            p.relative_to(self.workspace_root)
            for p in abs_dir_path.glob(pattern)
        ]
        self.logger.info(
            f"Successfully listed directory: {abs_dir_path} with pattern '{pattern}'. Found {len(relative_paths)} items."
        )
        return relative_paths
      except Exception as e:  # Catch potential errors during globbing or path conversion
        msg = f"Error listing directory {abs_dir_path} with pattern '{pattern}': {e}"
        self.logger.error(msg)
        raise FileManagerError(msg)

  def exists(self, rel_path: str | pathlib.Path) -> bool:
    """Checks if a path exists in the workspace.

    This method resolves the path and checks for its existence.
    It returns False if the path is invalid (e.g., outside workspace)
    or if it simply does not exist.

    Args:
      rel_path: The relative path (string or Path object) to check.

    Returns:
      True if the path exists within the workspace, False otherwise.
    """
    self.logger.debug(f"Attempting to check existence of path: {rel_path}")
    try:
      # _resolve_path will raise FileManagerError if path is malformed or outside workspace.
      # These are logged as errors by _resolve_path.
      abs_path = self._resolve_path(rel_path)
      with self.lock: # Lock during the actual check
        path_exists = abs_path.exists()
      self.logger.info(f"Path {abs_path} existence check returned: {path_exists}")
      return path_exists
    except FileManagerError:
      # This means _resolve_path failed; path is invalid or outside workspace.
      # Log message already handled by _resolve_path for specific error.
      self.logger.info(f"Path {rel_path} does not exist or is invalid/outside workspace.")
      return False

  def ensure_dir(self, rel_dir: str | pathlib.Path, *, exist_ok: bool = True) -> None:
    """Ensures that a directory (and its parents) exists in the workspace.

    Args:
      rel_dir: The relative path (string or Path object) to the directory.
      exist_ok: If True (default), do not raise an error if the directory
                already exists. If False, a FileManagerError is raised if
                the directory already exists.

    Raises:
      FileManagerError: If the path is invalid, if directory creation fails,
                        or if `exist_ok` is False and the directory already exists.
                        Also raised if a file exists at the given path.
    """
    self.logger.debug(
        f"Attempting to ensure directory exists: {rel_dir} (exist_ok: {exist_ok})"
    )
    abs_dir_path = self._resolve_path(rel_dir)
    with self.lock:
      try:
        # Path.mkdir will raise FileExistsError if path exists and is a file,
        # or if path is a dir and exist_ok=False.
        # It will raise NotADirectoryError if part of the parent path is a file.
        abs_dir_path.mkdir(parents=True, exist_ok=exist_ok)
        self.logger.info(f"Successfully ensured directory exists: {abs_dir_path}")
      except FileExistsError as e:
        # This error occurs if path exists and is a file, OR if path is a dir and exist_ok=False.
        if abs_dir_path.is_dir() and exist_ok:
          self.logger.debug(
              f"Directory {abs_dir_path} already exists and exist_ok=True. No action needed."
          )
          return # Not an error condition in this specific case.

        # If it's a file, or if it's a dir and exist_ok=False
        msg = f"Cannot create directory {abs_dir_path}: Path exists. It might be a file, or exist_ok=False. Original error: {e}"
        self.logger.error(msg)
        raise FileManagerError(msg)
      except OSError as e: # Catch other OS-level errors like permission denied
        msg = f"Error creating directory {abs_dir_path}: {e}"
        self.logger.error(msg)
        raise FileManagerError(msg)

  def move(
      self, src: str | pathlib.Path, dest: str | pathlib.Path, *, overwrite: bool = False
  ) -> None:
    """
    Moves a file or directory within the workspace.

    Args:
      src: The relative source path (string or Path object).
      dest: The relative destination path (string or Path object).
      overwrite: If True, overwrite the destination if it exists.
                 Defaults to False.

    Raises:
      FileManagerError: If paths are invalid, source does not exist,
                        destination exists and overwrite is False,
                        or if the move operation fails.
    """
    self.logger.debug(
        f"Attempting to move {src} to {dest} (overwrite: {overwrite})"
    )
    src_abs_path = self._resolve_path(src)
    dest_abs_path = self._resolve_path(dest)

    with self.lock:
      if not src_abs_path.exists():
        msg = f"Source path for move does not exist: {src_abs_path}"
        self.logger.error(msg)
        raise FileManagerError(msg)

      if dest_abs_path.exists():
        if not overwrite:
          msg = f"Destination path {dest_abs_path} for move exists and overwrite is False."
          self.logger.error(msg)
          raise FileManagerError(msg)
        # Overwrite is true, so delete existing destination.
        # This delete is already locked and logs appropriately.
        self.logger.debug(f"Overwrite is true. Deleting existing destination: {dest_abs_path}")
        try:
            self.delete(dest_abs_path.relative_to(self.workspace_root), recursive=True)
        except FileManagerError as e:
            # Log and re-raise if deletion failed
            self.logger.error(f"Failed to delete existing destination {dest_abs_path} during move: {e}")
            raise

      # Ensure parent directory of destination exists.
      # This uses the public ensure_dir which will try to acquire the lock again.
      # This is a potential deadlock if ensure_dir was not re-entrant.
      # However, our lock is re-entrant (threading.Lock is by default in Python 3,
      # but it's better to avoid nested acquire if not strictly needed).
      # For simplicity, let's ensure parent dir directly here.
      dest_parent_abs = dest_abs_path.parent
      if not dest_parent_abs.exists():
          self.logger.debug(f"Creating parent directory for destination: {dest_parent_abs}")
          dest_parent_abs.mkdir(parents=True, exist_ok=True)
      elif not dest_parent_abs.is_dir():
          msg = f"Cannot move: parent of destination '{dest_parent_abs}' exists and is not a directory."
          self.logger.error(msg)
          raise FileManagerError(msg)

      try:
        shutil.move(str(src_abs_path), str(dest_abs_path))
        self.logger.info(f"Successfully moved {src_abs_path} to {dest_abs_path}")
      except (OSError, shutil.Error) as e:
        msg = f"Error moving {src_abs_path} to {dest_abs_path}: {e}"
        self.logger.error(msg)
        raise FileManagerError(msg)
      # Note: Post-write hooks are typically for content changes. Move is more a location change.
      # If hooks were desired here, they'd need to be called for dest_abs_path.

  def copy(
      self, src: str | pathlib.Path, dest: str | pathlib.Path, *, overwrite: bool = False
  ) -> None:
    """
    Copies a file or directory within the workspace.

    Args:
      src: The relative source path (string or Path object).
      dest: The relative destination path (string or Path object).
      overwrite: If True, overwrite the destination if it exists.
                 Defaults to False.

    Raises:
      FileManagerError: If paths are invalid, source does not exist,
                        destination exists and overwrite is False,
                        or if the copy operation fails.
    """
    self.logger.debug(
        f"Attempting to copy {src} to {dest} (overwrite: {overwrite})"
    )
    src_abs_path = self._resolve_path(src)
    dest_abs_path = self._resolve_path(dest)

    with self.lock:
      if not src_abs_path.exists():
        msg = f"Source path for copy does not exist: {src_abs_path}"
        self.logger.error(msg)
        raise FileManagerError(msg)

      if dest_abs_path.exists():
        if not overwrite:
          msg = f"Destination path {dest_abs_path} for copy exists and overwrite is False."
          self.logger.error(msg)
          raise FileManagerError(msg)
        # Overwrite is true, so delete existing destination.
        self.logger.debug(f"Overwrite is true. Deleting existing destination: {dest_abs_path}")
        try:
            self.delete(dest_abs_path.relative_to(self.workspace_root), recursive=True)
        except FileManagerError as e:
            self.logger.error(f"Failed to delete existing destination {dest_abs_path} during copy: {e}")
            raise

      # Ensure parent directory of destination exists (similar to move)
      dest_parent_abs = dest_abs_path.parent
      if not dest_parent_abs.exists():
        self.logger.debug(f"Creating parent directory for destination: {dest_parent_abs}")
        dest_parent_abs.mkdir(parents=True, exist_ok=True)
      elif not dest_parent_abs.is_dir():
        msg = f"Cannot copy: parent of destination '{dest_parent_abs}' exists and is not a directory."
        self.logger.error(msg)
        raise FileManagerError(msg)

      try:
        if src_abs_path.is_file():
          shutil.copy2(str(src_abs_path), str(dest_abs_path))
          self.logger.info(f"Successfully copied file {src_abs_path} to {dest_abs_path}")
        elif src_abs_path.is_dir():
          shutil.copytree(str(src_abs_path), str(dest_abs_path))
          self.logger.info(f"Successfully copied directory {src_abs_path} to {dest_abs_path}")
        else:
          # This case handles things like broken symlinks that exist but are not file/dir
          msg = f"Source path {src_abs_path} is not a file or a directory (e.g., a broken symlink). Cannot copy."
          self.logger.error(msg)
          raise FileManagerError(msg)

        # Call post-write hooks if the destination is a file (copying a file, or a dir results in many files)
        # For simplicity, let's assume hooks are for individual file writes.
        # If copying a file, dest_abs_path is that file.
        # If copying a directory, hooks would ideally run for each file within.
        # The current hook signature is Callable[[Path], None], taking one path.
        # For directory copies, we might need a different hook strategy or skip them.
        # For now, call hooks only if a single file was copied.
        if src_abs_path.is_file(): # Check original source type
            for hook in self.post_write_hooks:
                hook_name_for_log = getattr(hook, 'name', str(hook))
                try:
                    self.logger.debug(f"Calling post-copy (file) hook {hook_name_for_log} for {dest_abs_path}")
                    hook(dest_abs_path)
                except Exception as e:
                    self.logger.error(
                        f"Post-copy (file) hook {hook_name_for_log} failed for {dest_abs_path}: {e}"
                    )

      except (OSError, shutil.Error) as e:
        msg = f"Error copying {src_abs_path} to {dest_abs_path}: {e}"
        self.logger.error(msg)
        raise FileManagerError(msg)
