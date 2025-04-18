# Image Converter Module
from PIL import Image
import io
import os
from loguru import logger
import pymupdf  # PyMuPDF
import logging

# Ensure logs directory exists and use it for logging
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "imgconv.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger.configure(
    handlers=[
        {"sink": LOG_FILE, "rotation": "10 MB", "retention": "1 day"},
        {"sink": lambda msg: print(msg, end=""), "level": "INFO"}
    ]
)

def _handle_jpeg(img, settings, save_kwargs):
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    if settings["optimize"]:
        save_kwargs['optimize'] = True
    save_kwargs['quality'] = settings.get("quality", 90)
    return img

def _handle_webp(img, settings, save_kwargs):
    if settings["quality"] is not None:
        save_kwargs['quality'] = settings["quality"]
    if not settings["compression"]:
        save_kwargs['lossless'] = True
    if settings["optimize"]:
        save_kwargs['method'] = 6
    return img

def _handle_png(img, settings, save_kwargs):
    if settings["optimize"]:
        save_kwargs['optimize'] = True
    if not settings["compression"] and settings["quality"] is not None:
        compression_level = max(0, min(9, 9 - (settings["quality"] // 11)))
        save_kwargs['compress_level'] = compression_level
    return img

def _handle_tiff(img, settings, save_kwargs):
    if settings["quality"] is not None:
        save_kwargs['compression'] = 'jpeg' if settings["quality"] < 90 else 'lzw'
    else:
        save_kwargs['compression'] = 'lzw'
    return img

def _handle_gif(img, settings, save_kwargs):
    if settings["optimize"]:
        save_kwargs['optimize'] = True
    return img

def _handle_bmp(img, settings, save_kwargs):
    if settings["bmp_compression"] and img.mode in ['RGB', 'RGBA']:
        save_kwargs['compression'] = 1
    return img

def _handle_avif(img, settings, save_kwargs):
    save_kwargs['quality'] = min(max(1, settings.get("quality", 75)), 100)
    save_kwargs['speed'] = settings["avif_speed"]
    return img

def _handle_heif(img, settings, save_kwargs):
    save_kwargs['quality'] = settings.get("quality", 80)
    return img

def _handle_ico(img, settings, save_kwargs):
    if img.width > 256 or img.height > 256:
        img.thumbnail((256, 256), Image.LANCZOS)
    return img

def _handle_tga(img, settings, save_kwargs):
    if settings.get("tga_compression"):
        save_kwargs['compression'] = "tga_rle"
    return img

def _handle_other(img, settings, save_kwargs):
    # For PPM, PBM, PNM, PGM, SGI, etc.
    return img

def _apply_format_settings(img, pil_format, settings, save_kwargs):
    match pil_format:
        case 'JPEG' | 'JPG':
            return _handle_jpeg(img, settings, save_kwargs)
        case 'WEBP':
            return _handle_webp(img, settings, save_kwargs)
        case 'PNG':
            return _handle_png(img, settings, save_kwargs)
        case 'TIFF':
            return _handle_tiff(img, settings, save_kwargs)
        case 'GIF':
            return _handle_gif(img, settings, save_kwargs)
        case 'BMP':
            return _handle_bmp(img, settings, save_kwargs)
        case 'AVIF':
            return _handle_avif(img, settings, save_kwargs)
        case 'HEIF' | 'HEIC':
            return _handle_heif(img, settings, save_kwargs)
        case 'ICO':
            return _handle_ico(img, settings, save_kwargs)
        case 'TGA':
            return _handle_tga(img, settings, save_kwargs)
        case 'PPM' | 'PBM' | 'PNM' | 'PGM' | 'SGI':
            return _handle_other(img, settings, save_kwargs)
        case _:
            return img

def convert_image(
    input_bytes: bytes, 
    target_format: str, 
    settings: dict
) -> bytes:
    """
    Convert image to target format with optional compression and optimize settings.
    
    Parameters:
    -----------
    input_bytes : bytes
        The source image data as bytes
    target_format : str
        The target image format (e.g., 'jpg', 'png', 'webp', 'avif', 'pdf')
    settings : dict
        Dictionary containing conversion settings:
        - remove_metadata (bool): Whether to strip metadata from the image
        - quality (int): Quality level (1-100)
        - optimize (bool): Whether to optimize the image
        - bmp_compression (bool): Whether to use RLE compression for BMP images
        - pdf_page_size (str): Page size for PDF conversion ('A4' or 'letter')
        - avif_speed (int): AVIF encoder speed (0-10)
        
    Returns:
    --------
    bytes
        The converted image data as bytes
    """
    logger.info(f"Starting image conversion: {target_format} with settings {settings}")
    
    # Special handling for PDF conversion
    if target_format.upper() == 'PDF':
        return convert_image_to_pdf(input_bytes, page_size=settings["pdf_page_size"])
    
    try:
        with Image.open(io.BytesIO(input_bytes)) as img:
            logger.info(f"Image opened successfully: {img.format} {img.size} {img.mode}")
            output_io = io.BytesIO()

            save_kwargs = {}
            if settings["remove_metadata"]:
                img.info = {}
            
            # Normalize target format for saving
            pil_format = target_format.upper()
            
            # Format-specific settings
            img = _apply_format_settings(img, pil_format, settings, save_kwargs)
            
            logger.info(f"Saving image with format {pil_format}, options: {save_kwargs}")
            img.save(output_io, format=pil_format, **save_kwargs)
            output_io.seek(0) # Reset stream position to the beginning
            return output_io.read()
            
    except Exception as e:
        logger.error(f"Image conversion error: {str(e)}", exc_info=True)
        # More detailed error information
        error_details = {
            "error": str(e),
            "error_type": type(e).__name__,
            "format": target_format,
            "input_size": len(input_bytes)
        }
        logger.error(f"Error details: {error_details}")
        raise ValueError(f"Image conversion failed: {str(e)}")

def convert_image_to_pdf(input_bytes: bytes, page_size: str = 'A4') -> bytes:
    """
    Convert an image to PDF using PyMuPDF (faster and more secure than ReportLab)
    """
    logger.info(f"Converting image to PDF with page size {page_size}")
    
    try:
        # Create a new PDF with a single page
        pdf_doc = pymupdf.open()  # Using the imported pymupdf instead of fitz
        
        if page_size.upper() == 'A4':
            # A4 in points (595 x 842)
            page = pdf_doc.new_page(width=595, height=842)
        else:
            # Letter size in points (612 x 792)
            page = pdf_doc.new_page(width=612, height=792)
            
        # Load the image with PIL first to handle different formats
        with Image.open(io.BytesIO(input_bytes)) as img:
            # Convert to RGB if RGBA (transparent images)
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            
            # Save as PNG in memory
            temp_img_io = io.BytesIO()
            img.save(temp_img_io, format='PNG')
            temp_img_io.seek(0)
            img_data = temp_img_io.read()
            
        # Insert image into PDF with proper scaling
        rect = page.rect  # Full page rect
        # Create margin (50 points)
        margin = 50
        rect.x0 += margin
        rect.y0 += margin
        rect.x1 -= margin
        rect.y1 -= margin
        
        # Insert the image, adjusting to fit within the defined rectangle
        page.insert_image(rect, stream=img_data)
        
        # Save the PDF to a bytes buffer
        output_io = io.BytesIO()
        pdf_doc.save(output_io)
        pdf_doc.close()
        output_io.seek(0)
        
        logger.info("PDF conversion completed successfully")
        return output_io.read()
            
    except Exception as e:
        logger.error(f"Image to PDF conversion error: {str(e)}", exc_info=True)
        raise ValueError(f"Image to PDF conversion failed: {str(e)}")