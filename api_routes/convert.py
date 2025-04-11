from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import magic
from workers.tasks import convert_file_task
import re, unicodedata, os

MAX_FILE_SIZE = 250 * 1024 * 1024  # 250MB

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
    remove_metadata: bool = Form(False),
    quality: int = Form(None),
    optimize: bool = Form(True),
    bmp_compression: bool = Form(True),
    pdf_page_size: str = Form("A4"),
    avif_speed: int = Form(6),
):
    
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
    
    # Capture the AsyncResult and get its ID
    result = convert_file_task.delay(sanitize_filename, contents, convert_to, remove_metadata, quality, optimize, bmp_compression, pdf_page_size, avif_speed)
    celery_task_id = result.id
    return {
        "celery_id": celery_task_id,
        "message": "Conversion starting"
    }
