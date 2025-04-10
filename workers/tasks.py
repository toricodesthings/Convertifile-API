# Task for converting files using Celery
from workers.celery_app import celery
from converter import imageconvert, videoconvert, audioconvert, documentconvert
import os, time

# Create a reference to the same temp directory used in the result endpoint
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_files")
os.makedirs(TEMP_DIR, exist_ok=True)

# Task for converting files using Celery
# This task will be called by the FastAPI app when a conversion request is made
@celery.task(bind=True)
def convert_file_task(self, filename, contents, convert_to, remove_metadata):
    task_id = self.request.id
    self.update_state(state='processing', meta={'progress': 15, 'message': 'Preparing'})
    time.sleep(1)
    ext = filename.split('.')[-1].lower() # Get the file extension
    converted_filename = f"{filename.rsplit('.', 1)[0]}.{convert_to}"
    
    # Update task state to indicate processing has started
    self.update_state(state='processing', meta={
        'progress': 20, 
        'filename': filename,
        'message': f'Starting'  # Add this line
    })
    time.sleep(1)
    try:
        # Dispatch to appropriate converter based on extension using match-case
        self.update_state(state='processing', meta={'progress': 50, 'message': f'Converting to {convert_to}'})
        time.sleep(1)
        match ext:
            case "jpeg" | "jpg" | "png" | "webp" | "bmp" | "tiff" | "gif" | "ico": 
                result = imageconvert.convert_image(contents, convert_to, remove_metadata)
            case "mp3" | "wav" | "aac" | "flac" | "ogg" | "opus" | "m4a" | "wma" | "amr" | "ac3":
                result = audioconvert.convert_audio(contents, convert_to, remove_metadata)
            case "mp4" | "mkv" | "mov" | "avi" | "webm" | "flv" | "wmv" | "mpeg":
                result = videoconvert.convert_video(contents, convert_to, remove_metadata)
            case "pdf" | "docx" | "txt" | "rtf":
                result = documentconvert.convert_document(contents, convert_to, remove_metadata)
            case _:
                raise ValueError(f"Unsupported file type: .{ext}")
        
        # Update progress before saving file
        self.update_state(state='processing', meta={'progress': 90, 'message': 'Saving conversion'})
        time.sleep(1)
        # Save the result to temp directory
        result_path = os.path.join(TEMP_DIR, f"{task_id}_{converted_filename}")
        with open(result_path, 'wb') as f:
            f.write(result)
            
        return {
            "status": "completed",
            "filename": f"{task_id}_{converted_filename}",
            "file_id": task_id,
            "original_name": converted_filename
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }