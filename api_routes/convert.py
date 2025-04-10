from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import magic
from workers.tasks import convert_file_task
import re

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
            detail="Suspicious filename detected"
        )
    
    contents = await file.read()
    file_size = len(contents)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size allowed is {MAX_FILE_SIZE/(1024*1024)}MB"
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
    result = convert_file_task.delay(file.filename, contents, convert_to, remove_metadata, quality, optimize, bmp_compression, pdf_page_size, avif_speed)
    celery_task_id = result.id
    return {
        "celery_id": celery_task_id,
        "message": "Conversion starting"
    }
