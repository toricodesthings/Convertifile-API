from fastapi import APIRouter
from workers.celery_app import celery
from celery.result import AsyncResult
import os

router = APIRouter()

def _find_output_file(task_id, temp_dir):
    for f in os.listdir(temp_dir):
        if f.startswith(task_id) and os.path.isfile(os.path.join(temp_dir, f)):
            return f
    return None

def _build_completed_response(task_id, filename):
    original_name = filename.replace(f"{task_id}_", "", 1)
    return {
        "status": "completed",
        "file_id": task_id,
        "filename": filename,
        "original_name": original_name
    }

def _build_failed_response(task_result):
    error = str(task_result.result) if task_result.result else "Unknown error"
    return {"status": "failed", "error": error}

def _build_processing_response(task_result):
    response = {
        "status": task_result.state.lower(),
    }
    if hasattr(task_result, 'info') and task_result.info:
        #if isinstance(task_result.info, dict) and 'message' in task_result.info:
            #response["status"] = 'processing'
        response["meta"] = task_result.info
    return response

@router.get("/{task_id}")
@router.get("/{task_id}/")  
async def get_status(task_id: str):
    """
    Get the status of a conversion task.
    
    This endpoint checks both Celery's task status and the existence of the output file.
    """
    TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_files")
    filename = _find_output_file(task_id, TEMP_DIR)
    task_result = AsyncResult(task_id, app=celery)

    if filename:
        return _build_completed_response(task_id, filename)

    if task_result.ready():
        filename = _find_output_file(task_id, TEMP_DIR)
        if filename:
            return _build_completed_response(task_id, filename)
        if task_result.successful():
            result = task_result.result
            return result if isinstance(result, dict) else {"status": "completed", "result": result}
        else:
            return _build_failed_response(task_result)
    else:
        return _build_processing_response(task_result)
