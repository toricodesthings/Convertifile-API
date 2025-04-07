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
    task_id = str(uuid4())
    contents = await file.read()
    convert_file_task.delay(task_id, file.filename, contents, convert_to, remove_metadata)
    return {"task_id": task_id, "message": "Conversion starting"}
