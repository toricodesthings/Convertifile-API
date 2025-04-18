from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import magic
from workers.tasks import convert_file_task
import re, unicodedata

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB

ALLOWED_MIME_PREFIXES = ['image/', 'audio/', 'video/', 'application/pdf', 'text/']
SUSPICIOUS_PATTERNS = [
    r'\.exe$', r'\.sh$', r'\.bat$', r'\.cmd$', r'\.php$', r'\.js$',
    r'\.dll$', r'\.vbs$', r'\.py$', r'\.(exe|sh|bat|cmd|php|js|dll)\.', 
    r'<script', r'eval\(', r'system\(', r'exec\('
]

def is_suspicious_filename(filename: str) -> bool:
    """Check if filename has suspicious patterns or double extensions"""
    filename = filename.lower()
    
    # Check against suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, filename):
            return True
    
    return False

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to ensure it's safe and clean.
    
    1. Normalize unicode characters 
    2. Remove non-alphanumeric chars except for safe ones
    3. Limit length
    4. Ensure filename doesn't start/end with spaces or periods
    """
    # Normalize unicode characters
    filename = unicodedata.normalize('NFKD', filename)
    
    # Get name and extension parts
    name_parts = filename.rsplit('.', 1)
    name = name_parts[0]
    extension = name_parts[1].lower() if len(name_parts) > 1 else ''
    
    # Replace dangerous characters with underscores, keeping safe chars
    name = re.sub(r'[^\w\-. ]', '_', name)
    
    # Remove consecutive underscores/spaces
    name = re.sub(r'_{2,}', '_', name)
    name = re.sub(r' {2,}', ' ', name)
    
    # Trim to reasonable length (100 chars for name + extension)
    max_name_length = 100 - len(extension) - 1 if extension else 100
    name = name[:max_name_length]
    
    # Ensure name doesn't start/end with space, period, or underscore
    name = name.strip(' ._')
    
    # If name is empty after sanitization, use a default
    if not name:
        name = "converted_image"
    
    # Reconstruct filename with extension if present
    return f"{name}.{extension}" if extension else name

router = APIRouter()

@router.post("/")
async def convert_file(
    file: UploadFile = File(...),
    convert_to: str = Form(...),

    # Image conversion options
    remove_metadata: bool = Form(False),
    compression: bool = Form(False),
    quality: int = Form(None),
    optimize: bool = Form(True),
    bmp_compression: bool = Form(True),
    tga_compression: bool = Form(True),
    pdf_page_size: str = Form("A4"),
    avif_speed: int = Form(6),

    # Audio conversion options
    audio_remove_metadata: bool = Form(False),
    audio_codec: str = Form(None),
    audio_bitrate: str = Form(None),
    audio_sample_rate: int = Form(None),
    audio_channels: int = Form(2),
    audio_lossless: bool = Form(False),
    audio_compression_level: int = Form(None),

    # Video conversion options
    video_remove_metadata: bool = Form(False),
    video_codec: str = Form(None),
    video_crf: int = Form(None),
    video_profile: str = Form(None),
    video_level: str = Form(None),
    video_speed: str = Form(None),
    video_bitrate: str = Form(None),
    video_width: int = Form(None),
    video_height: int = Form(None),
    video_fps: int = Form(None),
) -> dict:
    
    """
    Convert a file to a different format using a background task.

    Returns:
    --------
    task_id : str
        Unique identifier for the conversion task.
    message : str
    
    """
    
    # Check if the filename is suspicious
    if is_suspicious_filename(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Unallowed filename."
        )
        
    sanitized_filename = sanitize_filename(file.filename)
    
    contents = await file.read()
    file_size = len(contents)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size allowed is {MAX_FILE_SIZE/(1024*1024)}MB"
        )
    
    # 4. Verify MIME type
    mime = magic.Magic(mime=True)
    # Allow only certain MIME type prefixes
    if not any(mime.from_buffer(contents).startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type."
        )
        
        # 5. Check for common binary signatures
    suspicious_signatures = [
        b'MZ',           # Windows executable
        b'\x7FELF',      # ELF files (Unix/Linux executables)
        b'#!',           # Shebang (script files)
        b'<?php',        # PHP scripts
        b'<script',      # JavaScript
    ]
    
    for sig in suspicious_signatures:
        if sig in contents[:100]:  # Check first 100 bytes
            raise HTTPException(
                status_code=400,
                detail="File rejected due to possible malicious content"
            )
    
    # Determine conversion settings based on type
    if convert_to.lower() in ["mp3", "wav", "flac", "aac", "ogg", "m4a", "opus"]:  # audio formats
        conversion_settings = {
            "remove_metadata": audio_remove_metadata,
            "codec": audio_codec,
            "bitrate": audio_bitrate,
            "sample_rate": audio_sample_rate,
            "channels": audio_channels,
            "lossless": audio_lossless,
            "compression_level": audio_compression_level,
        }
    elif convert_to.lower() in ["mp4", "mov", "avi", "mkv", "webm", "flv", "wmv"]:  # video formats
        conversion_settings = {
            "remove_metadata": video_remove_metadata,
            "codec": video_codec,
            "crf": video_crf,
            "profile": video_profile,
            "level": video_level,
            "speed": video_speed,
            "bitrate": video_bitrate,
            "width": video_width,
            "height": video_height,
            "fps": video_fps,
        }
    else:
        conversion_settings = {
            "remove_metadata": remove_metadata,
            "compression": compression,
            "quality": quality,
            "optimize": optimize,
            "bmp_compression": bmp_compression,
            "tga_compression": tga_compression,
            "pdf_page_size": pdf_page_size,
            "avif_speed": avif_speed
        }
    
    # Capture the AsyncResult and get its ID, run the task
    result = convert_file_task.delay(sanitized_filename, contents, convert_to, conversion_settings)
    celery_task_id = result.id
    return {
        "celery_id": celery_task_id,
        "message": "Conversion starting"
    }
