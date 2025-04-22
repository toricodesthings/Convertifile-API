# Image Converter Module
from PIL import Image
import io
from pathlib import Path
from loguru import logger
import pymupdf  # PyMuPDF

# Ensure logs directory exists and use it for logging using Pathlib
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "imgconv.log"

# Add a handler to the existing logger for this module only
logger.add(LOG_FILE, rotation="10 MB", retention="1 day", filter=lambda record: record["extra"].get("module") == "imageconvert")

# Create a module-specific logger instead of using the global one
img_logger = logger.bind(module="imageconvert")

def _handle_jpeg(img, settings, save_kwargs):
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    if settings.get("optimize"):
        save_kwargs['optimize'] = True
    save_kwargs['quality'] = settings.get("quality", 90)
    return img

def _handle_webp(img, settings, save_kwargs):
    quality = settings.get("quality")
    if quality is not None:
        save_kwargs['quality'] = quality
    if not settings.get("compression", True):
        save_kwargs['lossless'] = True
    if settings.get("optimize"):
        save_kwargs['method'] = 6
    return img

def _handle_png(img, settings, save_kwargs):
    if settings.get("optimize"):
        save_kwargs['optimize'] = True
    quality = settings.get("quality")
    if not settings.get("compression", True) and quality is not None:
        compression_level = max(0, min(9, 9 - (quality // 11)))
        save_kwargs['compress_level'] = compression_level
    return img

def _handle_tiff(img, settings, save_kwargs):
    quality = settings.get("quality")
    if quality is not None:
        save_kwargs['compression'] = 'jpeg' if quality < 90 else 'lzw'
    else:
        save_kwargs['compression'] = 'lzw'
    return img

def _handle_bmp(img, settings, save_kwargs):
    if settings.get("bmp_compression") and img.mode in ['RGB', 'RGBA']:
        save_kwargs['compression'] = 1
    return img

def _handle_avif(img, settings, save_kwargs):
    save_kwargs['quality'] = settings.get("quality", 80)
    save_kwargs['speed'] = settings.get("avif_speed", 5)
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
    img_logger.info(f"Starting image conversion: {target_format} with settings {settings}")

    # Special handling for PDF conversion
    if target_format.upper() == 'PDF':
        return convert_image_to_pdf(input_bytes, page_size=settings.get("pdf_page_size", "A4"))

    try:
        with Image.open(io.BytesIO(input_bytes)) as img:
            img_logger.info(f"Image opened successfully: {img.format} {img.size} {img.mode}")
            output_io = io.BytesIO()
            save_kwargs = {}
            if settings.get("remove_metadata"):
                img.info = {}

            pil_format = (
                "JPEG" 
                if target_format.lower() in ("jpg", "jpeg") 
                else target_format.upper()
            )
            
            img = _apply_format_settings(img, pil_format, settings, save_kwargs)

            img_logger.info(f"Saving image with format {pil_format}, options: {save_kwargs}")
            img.save(output_io, format=pil_format, **save_kwargs)
            output_io.seek(0)
            return output_io.read()

    except Exception as e:
        img_logger.error(f"Image conversion error: {str(e)}", exc_info=True)
        error_details = {
            "error": str(e),
            "error_type": type(e).__name__,
            "format": target_format,
            "input_size": len(input_bytes)
        }
        img_logger.error(f"Error details: {error_details}")
        raise ValueError(f"Image conversion failed: {str(e)}")

def convert_image_to_pdf(input_bytes: bytes, page_size: str = 'A4') -> bytes:
    """
    Convert an image to PDF using PyMuPDF (faster and more secure than ReportLab)
    The image will be scaled to fit the page (A4, Letter, A3, A5, Legal, Tabloid) with no added margins.
    """
    img_logger.info(f"Converting image to PDF with page size {page_size}")

    # Define more page sizes (dimensions in points: 1pt = 1/72 inch)
    PAGE_SIZES = {
        "A3": (842, 1191),
        "A4": (595, 842),
        "A5": (420, 595),
        "LETTER": (612, 792),
        "LEGAL": (612, 1008),
        "TABLOID": (792, 1224)
    }

    try:
        pdf_doc = pymupdf.open()
        size_key = page_size.upper()
        page_width, page_height = PAGE_SIZES.get(size_key, PAGE_SIZES["A4"])
        page = pdf_doc.new_page(width=page_width, height=page_height)

        with Image.open(io.BytesIO(input_bytes)) as img:
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background

            img_width, img_height = img.size
            img_aspect = img_width / img_height
            page_aspect = page_width / page_height

            # Scale image to fit page, preserving aspect ratio, no margins
            if img_aspect > page_aspect:
                draw_width = page_width
                draw_height = page_width / img_aspect
                x0 = 0
                y0 = (page_height - draw_height) / 2
            else:
                draw_height = page_height
                draw_width = page_height * img_aspect
                x0 = (page_width - draw_width) / 2
                y0 = 0
            x1 = x0 + draw_width
            y1 = y0 + draw_height
            rect = pymupdf.Rect(x0, y0, x1, y1)

            temp_img_io = io.BytesIO()
            img.save(temp_img_io, format='PNG')
            temp_img_io.seek(0)
            img_data = temp_img_io.read()

        page.insert_image(rect, stream=img_data)

        output_io = io.BytesIO()
        pdf_doc.save(output_io)
        pdf_doc.close()
        output_io.seek(0)

        img_logger.info("PDF conversion completed successfully")
        return output_io.read()

    except Exception as e:
        img_logger.error(f"Image to PDF conversion error: {str(e)}", exc_info=True)
        raise ValueError(f"Image to PDF conversion failed: {str(e)}")