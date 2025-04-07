from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

# Create a temp directory in the project folder
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_files")
os.makedirs(TEMP_DIR, exist_ok=True)

router = APIRouter()

@router.get("/{file_id}")
async def download_result(file_id: str):
    """
    Download the converted file.
    This endpoint checks if the file exists in the temp directory and returns it.

    Args:
        file_id (str): The unique identifier for the file to be downloaded.

    Raises:
        HTTPException: If the file is not found or has expired.

    Returns:
        FileResponse: The converted file to be downloaded.
    """
    for file in os.listdir(TEMP_DIR):
        if file.startswith(file_id):
            file_path = os.path.join(TEMP_DIR, file)
            if os.path.exists(file_path):
                return FileResponse(path=file_path, filename=file)
    raise HTTPException(status_code=404, detail="File not found or expired")