from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import magic
from workers.tasks import convert_file_task
import re, unicodedata

MAX_FILE_SIZE_IMAGE = 200 * 1024 * 1024    # 200MB
MAX_FILE_SIZE_VIDEO = 1024 * 1024 * 1024   # 1GB
MAX_FILE_SIZE_AUDIO = 500 * 1024 * 1024    # 500MB
MAX_FILE_SIZE_DOC   = 100 * 1024 * 1024    # 100MB

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

def get_file_category(mime_type: str, convert_to: str) -> str:
    """Determine file category based on mime type or convert_to."""
    audio_formats = ["mp3", "wav", "flac", "aac", "ogg", "m4a", "opus"]
    video_formats = ["mp4", "mov", "avi", "mkv", "webm", "flv", "wmv"]
    doc_formats = ["pdf", "docx", "text", "txt"]
    if mime_type.startswith("image/"):
        return "image"
    elif mime_type.startswith("video/") or convert_to.lower() in video_formats:
        return "video"
    elif mime_type.startswith("audio/") or convert_to.lower() in audio_formats:
        return "audio"
    elif mime_type.startswith("application/pdf") or mime_type.startswith("text/") or convert_to.lower() in doc_formats:
        return "doc"
    else:
        return "image"  # Default fallback

def check_file_size(contents: bytes, mime_type: str, convert_to: str):
    category = get_file_category(mime_type, convert_to)
    if category == "image":
        max_size = MAX_FILE_SIZE_IMAGE
    elif category == "video":
        max_size = MAX_FILE_SIZE_VIDEO
    elif category == "audio":
        max_size = MAX_FILE_SIZE_AUDIO
    elif category == "doc":
        max_size = MAX_FILE_SIZE_DOC
    else:
        max_size = MAX_FILE_SIZE_IMAGE
    file_size = len(contents)
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size allowed for {category} is {max_size // (1024*1024)}MB"
        )

def check_mime_type(contents: bytes):
    mime = magic.Magic(mime=True)
    if not any(mime.from_buffer(contents).startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type."
        )
    
    return mime.from_buffer(contents)

def check_suspicious_signatures(contents: bytes):
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

def get_conversion_settings(convert_to: str, form_data: dict) -> dict:
    audio_formats = ["mp3", "wav", "flac", "aac", "ogg", "m4a", "opus"]
    video_formats = ["mp4", "mov", "avi", "mkv", "webm", "flv", "wmv"]
    doc_formats = ["pdf", "docx", "text", "txt"]
    if convert_to.lower() in audio_formats:
        return {
            "remove_metadata": form_data["audio_remove_metadata"],
            "codec": form_data["audio_codec"],
            "bitrate": form_data["audio_bitrate"],
            "sample_rate": form_data["audio_sample_rate"],
            "channels": form_data["audio_channels"],
            "compression_level": form_data["audio_compression_level"],
        }
    elif convert_to.lower() in video_formats:
        return {
            "remove_metadata": form_data["video_remove_metadata"],
            "codec": form_data["video_codec"],
            "crf": form_data["video_crf"],
            "profile": form_data["video_profile"],
            "level": form_data["video_level"],
            "speed": form_data["video_speed"],
            "bitrate": form_data["video_bitrate"],
            "fps": form_data["video_fps"],
        }
    elif convert_to.lower() in doc_formats:
        return {
            "dpi": form_data["dpi"],
            "quality": form_data["doc_quality"]
        }
    else:
        return {
            "remove_metadata": form_data["remove_metadata"],
            "compression": form_data["compression"],
            "quality": form_data["quality"],
            "optimize": form_data["optimize"],
            "bmp_compression": form_data["bmp_compression"],
            "tga_compression": form_data["tga_compression"],
            "pdf_page_size": form_data["pdf_page_size"],
            "avif_speed": form_data["avif_speed"]
        }

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
    audio_compression_level: int = Form(None),

    # Video conversion options
    video_remove_metadata: bool = Form(False),
    video_codec: str = Form(None),
    video_crf: int = Form(None),
    video_profile: str = Form(None),
    video_level: str = Form(None),
    video_speed: str = Form(None),
    video_bitrate: str = Form(None),
    video_fps: int = Form(None),
    
    # Document conversion options
    dpi : int = Form(200),
    doc_quality : int = Form(None),
) -> dict:
    """
    Convert a file to a different format using a background task.

    Returns:
    --------
    task_id : str
        Unique identifier for the conversion task.
    message : str
    """
    if is_suspicious_filename(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Unallowed filename."
        )
    sanitized_filename = sanitize_filename(file.filename)
    contents = await file.read()
    
    check_suspicious_signatures(contents)
    mime_type = check_mime_type(contents)
    check_file_size(contents, mime_type, convert_to)

    form_data = {
        "remove_metadata": remove_metadata,
        "compression": compression,
        "quality": quality,
        "optimize": optimize,
        "bmp_compression": bmp_compression,
        "tga_compression": tga_compression,
        "pdf_page_size": pdf_page_size,
        "avif_speed": avif_speed,
        "audio_remove_metadata": audio_remove_metadata,
        "audio_codec": audio_codec,
        "audio_bitrate": audio_bitrate,
        "audio_sample_rate": audio_sample_rate,
        "audio_channels": audio_channels,
        "audio_compression_level": audio_compression_level,
        "video_remove_metadata": video_remove_metadata,
        "video_codec": video_codec,
        "video_crf": video_crf,
        "video_profile": video_profile,
        "video_level": video_level,
        "video_speed": video_speed,
        "video_bitrate": video_bitrate,
        "video_fps": video_fps,
        "dpi": dpi,
        "doc_quality": doc_quality,
    }
    conversion_settings = get_conversion_settings(convert_to, form_data)

    result = convert_file_task.delay(sanitized_filename, contents, convert_to, conversion_settings)
    celery_task_id = result.id
    return {
        "celery_id": celery_task_id,
        "message": "Conversion starting"
    }
