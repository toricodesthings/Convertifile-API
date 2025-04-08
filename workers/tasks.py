# Task for converting files using Celery
from workers.celery_app import celery
from converter import imageconvert, videoconvert, audioconvert, documentconvert
import os

# Create a reference to the same temp directory used in the result endpoint
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_files")
os.makedirs(TEMP_DIR, exist_ok=True)

# Task for converting files using Celery
# This task will be called by the FastAPI app when a conversion request is made
@celery.task(bind=True)

# Function to convert files
def convert_file_task(self, task_id, filename, contents, convert_to, remove_metadata):
    ext = filename.split('.')[-1].lower() # Get the file extension
    converted_filename = f"{filename.rsplit('.', 1)[0]}.{convert_to}"
    
    # Update task state to indicate processing has started
    self.update_state(state='PROCESSING', meta={'progress': 10, 'filename': filename})
    
    try:
        # Dispatch to appropriate converter based on extension using match-case
        self.update_state(state='PROCESSING', meta={'progress': 40, 'message': f'Converting {ext} to {convert_to}'})
        match ext:
            case "jpeg" | "png" | "webp" | "bmp" | "tiff" | "gif" | "ico": 
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
        self.update_state(state='PROCESSING', meta={'progress': 80, 'message': 'Saving converted file'})
        
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