import os
import logging
import pathlib
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field

from scriptoria.file_manager import FileManager, FileManagerError

# --- Basic Setup ---
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Scriptoria Agent API",
    description="API for file management operations within a secure workspace.",
    version="1.0.0",
)

# --- FileManager Initialization ---
# Determine workspace root. Use environment variable or a default.
workspace_env = os.getenv("SCRIPTORIA_WORKSPACE")
if not workspace_env:
    logger.warning("SCRIPTORIA_WORKSPACE environment variable not set. Defaulting to '/tmp/scriptoria_workspace'.")
    workspace_root = pathlib.Path("/tmp/scriptoria_workspace")
else:
    workspace_root = pathlib.Path(workspace_env)

# Create the workspace directory if it doesn't exist
workspace_root.mkdir(parents=True, exist_ok=True)
logger.info(f"Using workspace root: {workspace_root.resolve()}")

# Instantiate the file manager
file_manager = FileManager(workspace_root=workspace_root, logger=logger)


# --- API Models ---
class MoveFileRequest(BaseModel):
    """Request model for the /move-file endpoint."""
    source_path: str = Field(
        ...,
        description="The relative path to the source file or directory to be moved.",
        examples=["path/to/source.txt"],
    )
    destination_path: str = Field(
        ...,
        description="The relative path to the destination.",
        examples=["path/to/destination.txt"],
    )
    overwrite: bool = Field(
        default=False,
        description="If True, overwrite the destination if it already exists.",
    )


# --- API Endpoints ---
@app.post("/move-file", status_code=200)
async def move_file_endpoint(payload: MoveFileRequest):
    """
    Moves a file or directory from a source path to a destination path
    within the agent's workspace.
    """
    try:
        logger.info(f"Received request to move '{payload.source_path}' to '{payload.destination_path}' (overwrite: {payload.overwrite})")
        file_manager.move_file(
            src=payload.source_path,
            dest=payload.destination_path,
            overwrite=payload.overwrite,
        )
        return {
            "message": f"Successfully moved '{payload.source_path}' to '{payload.destination_path}'."
        }
    except FileManagerError as e:
        # Log the specific file manager error
        logger.error(f"FileManagerError during move operation: {e}")
        # Return a moveuser-friendly error message
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"An unexpected error occurred during the move operation for '{payload.source_path}'.")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.get("/")
async def read_root():
    """A simple endpoint to confirm the API is running."""
    return {"message": "Scriptoria Agent API is running."}
