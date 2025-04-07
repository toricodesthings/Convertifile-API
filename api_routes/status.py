from fastapi import APIRouter
from workers.celery_app import celery
from celery.result import AsyncResult
import os

router = APIRouter()

@router.get("/{task_id}")
async def get_status(task_id: str):
    """
    Get the status of a conversion task.
    
    This endpoint checks both Celery's task status and the existence of the output file.
    """
    # First check if the file already exists in the temp directory
    TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_files")
    
    # Check if any file starting with the task_id exists in TEMP_DIR
    output_file_exists = any(f.startswith(task_id) for f in os.listdir(TEMP_DIR) if os.path.isfile(os.path.join(TEMP_DIR, f)))
    
    # Get the task result from Celery
    task_result = AsyncResult(task_id, app=celery)
    
    # If file exists but Celery hasn't updated the status yet, override with completed status
    if output_file_exists:
        # Find the actual filename for the task
        for f in os.listdir(TEMP_DIR):
            if f.startswith(task_id) and os.path.isfile(os.path.join(TEMP_DIR, f)):
                filename = f
                original_name = f.replace(f"{task_id}_", "", 1)
                return {
                    "status": "completed",
                    "file_id": task_id,
                    "filename": filename,
                    "original_name": original_name
                }
    
    # Return task state from Celery
    if task_result.ready():
        if task_result.successful():
            # Return the actual result data
            result = task_result.result
            return result if isinstance(result, dict) else {"status": "completed", "result": result}
        else:
            # Task failed
            error = str(task_result.result) if task_result.result else "Unknown error"
            return {"status": "failed", "error": error}
    else:
        # Task still running
        return {"status": task_result.state.lower()}
