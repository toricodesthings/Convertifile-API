from fastapi import APIRouter, UploadFile, File, Form
from workers.tasks import convert_file_task
from uuid import uuid4

router = APIRouter()

@router.post("/")
async def convert_file(
    file: UploadFile = File(...),
    convert_to: str = Form(...),
    remove_metadata: bool = Form(False)
):
    
    """
    Convert a file to a different format using a background task.

    Returns:
    --------
    task_id : str
        Unique identifier for the conversion task.
    message : str
    
    """
    contents = await file.read()
    
    # Capture the AsyncResult and get its ID
    result = convert_file_task.delay(file.filename, contents, convert_to, remove_metadata)
    celery_task_id = result.id
    
    return {
        "celery_id": celery_task_id,  # Celery's internal ID for precise status tracking
        "message": "Conversion starting"
    }
