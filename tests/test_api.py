import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import pathlib
import sys

# Ensure the app's root directory is in the Python path
# This allows us to import `scriptoria` even when running pytest from the root.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


# We need to make sure the app is loaded before running tests
# This also means we need to control the workspace for tests.
# We can do this by setting the environment variable *before* importing the app.
TEST_WORKSPACE_ROOT = "/tmp/test_workspace"
os.environ["SCRIPTORIA_WORKSPACE"] = TEST_WORKSPACE_ROOT

# Now, import the app
from scriptoria.api import app, file_manager
from scriptoria.file_manager import FileManagerError

# Fixture for the test client
@pytest.fixture
def client():
    """A TestClient instance for the FastAPI app."""
    return TestClient(app)

# Fixture to manage the test workspace filesystem using pyfakefs
@pytest.fixture
def fs(fs): # fs is the pyfakefs fixture
    """
    Manage the fake filesystem for tests.
    This creates the test workspace root before each test.
    """
    # pyfakefs creates a new fake filesystem for each test.
    # We need to ensure our test workspace directory exists within it.
    fs.create_dir(TEST_WORKSPACE_ROOT)
    yield fs
    # No cleanup needed, pyfakefs handles it.


def test_read_root(client):
    """Test the root endpoint to ensure the API is running."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Scriptoria Agent API is running."}


def test_move_file_success(client, fs):
    """Test successfully moving a file."""
    # Setup: Create a source file in the fake filesystem
    source_path_str = "source.txt"
    dest_path_str = "destination.txt"
    source_file = file_manager.workspace_root / source_path_str
    fs.create_file(source_file, contents="Hello, World!")

    # Make the API call
    response = client.post(
        "/move-file",
        json={"source_path": source_path_str, "destination_path": dest_path_str},
    )

    # Assertions
    assert response.status_code == 200
    assert "Successfully moved" in response.json()["message"]
    assert not fs.exists(source_file)
    assert fs.exists(file_manager.workspace_root / dest_path_str)
    with open(file_manager.workspace_root / dest_path_str) as f:
        assert f.read() == "Hello, World!"


def test_move_file_to_directory_success(client, fs):
    """Test successfully moving a file into an existing directory."""
    source_path_str = "file_to_move.txt"
    dest_dir_str = "my_dir"
    fs.create_file(file_manager.workspace_root / source_path_str, contents="Move me")
    fs.create_dir(file_manager.workspace_root / dest_dir_str)

    response = client.post(
        "/move-file",
        json={"source_path": source_path_str, "destination_path": dest_dir_str},
    )

    assert response.status_code == 200
    assert not fs.exists(file_manager.workspace_root / source_path_str)
    final_dest_path = file_manager.workspace_root / dest_dir_str / source_path_str
    assert fs.exists(final_dest_path)
    with open(final_dest_path) as f:
        assert f.read() == "Move me"


def test_move_file_overwrite_success(client, fs):
    """Test successfully moving a file with overwrite=True."""
    source_path_str = "source.txt"
    dest_path_str = "destination.txt"
    fs.create_file(file_manager.workspace_root / source_path_str, contents="New Content")
    fs.create_file(file_manager.workspace_root / dest_path_str, contents="Old Content")

    response = client.post(
        "/move-file",
        json={
            "source_path": source_path_str,
            "destination_path": dest_path_str,
            "overwrite": True,
        },
    )

    assert response.status_code == 200
    assert not fs.exists(file_manager.workspace_root / source_path_str)
    dest_file = file_manager.workspace_root / dest_path_str
    assert fs.exists(dest_file)
    with open(dest_file) as f:
        assert f.read() == "New Content"


def test_move_file_source_not_found(client, fs):
    """Test moving a file that does not exist."""
    response = client.post(
        "/move-file",
        json={"source_path": "non_existent.txt", "destination_path": "dest.txt"},
    )

    assert response.status_code == 400
    assert "Source path for move does not exist" in response.json()["detail"]


def test_move_file_destination_exists_no_overwrite(client, fs):
    """Test moving a file when destination exists and overwrite is False."""
    source_path_str = "source.txt"
    dest_path_str = "destination.txt"
    fs.create_file(file_manager.workspace_root / source_path_str, contents="Source")
    fs.create_file(file_manager.workspace_root / dest_path_str, contents="Destination")

    response = client.post(
        "/move-file",
        json={
            "source_path": source_path_str,
            "destination_path": dest_path_str,
            "overwrite": False,
        },
    )

    assert response.status_code == 400
    assert "Destination path" in response.json()["detail"]
    assert "exists and overwrite is False" in response.json()["detail"]
    # Ensure files were not modified
    assert fs.exists(file_manager.workspace_root / source_path_str)
    with open(file_manager.workspace_root / dest_path_str) as f:
        assert f.read() == "Destination"


def test_move_file_path_traversal_attack(client, fs):
    """Test for path traversal attempts."""
    payloads = [
        {"source_path": "../../../etc/passwd", "destination_path": "dest.txt"},
        {"source_path": "source.txt", "destination_path": "../../../etc/passwd"},
    ]
    fs.create_file(file_manager.workspace_root / "source.txt")

    for payload in payloads:
        response = client.post("/move-file", json=payload)
        assert response.status_code == 400
        assert "must be relative and not contain '..'" in response.json()["detail"]


def test_move_file_unexpected_error(client, fs):
    """Test handling of unexpected server errors during move."""
    # Create a source file
    source_path_str = "source.txt"
    dest_path_str = "destination.txt"
    fs.create_file(file_manager.workspace_root / source_path_str, contents="Content")

    # Mock the file_manager.move_file to raise a generic Exception
    with patch.object(file_manager, 'move_file', side_effect=Exception("A wild error appears!")) as mock_move:
        response = client.post(
            "/move-file",
            json={"source_path": source_path_str, "destination_path": dest_path_str},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "An internal server error occurred."
        mock_move.assert_called_once()


def test_move_file_invalid_payload(client):
    """Test with a malformed payload (missing required fields)."""
    response = client.post(
        "/move-file",
        json={"source_path": "some_file.txt"}, # Missing destination_path
    )
    # FastAPI's automatic validation should catch this.
    assert response.status_code == 422 # Unprocessable Entity
    # The response body contains details about the validation error
    assert "destination_path" in response.text
    assert "Field required" in response.text


def test_app_initialization_no_workspace_env(monkeypatch, caplog):
    """
    Test that the app initializes correctly and logs a warning
    when the SCRIPTORIA_WORKSPACE env var is not set.
    """
    # Remove the environment variable
    monkeypatch.delenv("SCRIPTORIA_WORKSPACE", raising=False)

    # We need to reload the app module to re-trigger the initialization logic
    import importlib
    from scriptoria import api
    importlib.reload(api)

    # Create a client with the reloaded app
    reloaded_client = TestClient(api.app)

    # Make a request to ensure it's working
    response = reloaded_client.get("/")
    assert response.status_code == 200

    # Check that the warning was logged
    assert "SCRIPTORIA_WORKSPACE environment variable not set" in caplog.text
    assert "Defaulting to '/tmp/scriptoria_workspace'" in caplog.text

    # Restore the original state by reloading the module again
    # This is important so other tests are not affected
    os.environ["SCRIPTORIA_WORKSPACE"] = TEST_WORKSPACE_ROOT
    importlib.reload(api)
