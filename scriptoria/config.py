"""Environment-driven configuration for the Scriptoria agent shell.

Scriptoria never imports cortex-os code: the Library is reached only over
HTTP (the one boundary), so the Library's canonical home can move without
touching this repo.
"""

import os
import pathlib


def library_url() -> str:
    """Base URL of the Cortex OS daemon (The Library)."""
    return os.environ.get("LIBRARY_URL", "http://localhost:8000").rstrip("/")


def cortex_api_token() -> str:
    """Bearer token the Library daemon expects on mutating requests."""
    return os.environ.get("CORTEX_API_TOKEN", "").strip()


def scriptoria_api_token() -> str:
    """Bearer token required by Scriptoria's own REST API (GPT actions)."""
    return os.environ.get("SCRIPTORIA_API_TOKEN", "").strip()


def workspaces_root() -> pathlib.Path:
    """Root directory holding the scriptorium's drafting workspaces."""
    default = pathlib.Path.home() / "agents" / "workspaces"
    return pathlib.Path(os.environ.get("SCRIPTORIA_WORKSPACES_ROOT", str(default)))
