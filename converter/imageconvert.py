# Image Converter Module
from PIL import Image
import io
from loguru import logger
import pymupdf  # PyMuPDF
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("imgconv.log"),
        logging.StreamHandler()
    ]
)

logger.configure(
    handlers=[
        {"sink": "app.log", "rotation": "10 MB", "retention": "1 day"},
        {"sink": lambda msg: print(msg, end=""), "level": "INFO"}
    ]
)

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
            match pil_format:
                case 'JPEG' | 'JPG':
                    pil_format = 'JPEG'  # Ensure consistent format name
                    # Handle RGBA to RGB conversion (JPEG doesn't support alpha channel)
                    if img.mode == 'RGBA':
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        # Paste the image using the alpha channel as mask
                        background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
                        img = background
                        
                    # JPEG optimization settings
                    if settings["optimize"]:
                        save_kwargs['optimize'] = True
                    # JPEG quality: 1-100 (higher is better quality but larger file)
                    if "quality" in settings and settings["quality"] is not None:
                        save_kwargs['quality'] = settings["quality"]
                    else:
                        save_kwargs['quality'] = 90 
                
                case 'WEBP':
                    # WebP quality: 1-100 (higher is better quality but larger file)
                    if settings["quality"] is not None:
                        save_kwargs['quality'] = settings["quality"]
                    
                    # WebP lossless option
                    if not settings["compression"]:
                        save_kwargs['lossless'] = True
                    
                    if settings["optimize"]:
                        save_kwargs['method'] = 6  
                
                case 'PNG':
                    # PNG uses lossless compression
                    if settings["optimize"]:
                        save_kwargs['optimize'] = True
                        
                    if not settings["compression"] and settings["quality"] is not None:
                        # Convert quality (1-100) to compression level (0-9)
                        compression_level = max(0, min(9, 9 - (settings["quality"] // 11)))
                        save_kwargs['compress_level'] = compression_level
                
                case 'TIFF':
                    if settings["quality"] is not None:
                        save_kwargs['compression'] = 'jpeg' if settings["quality"] < 90 else 'lzw'
                    else:
                        save_kwargs['compression'] = 'lzw'  # Default compression
                
                case 'GIF':
                    if settings["optimize"]:
                        save_kwargs['optimize'] = True
                
                case 'BMP':
                    if settings["bmp_compression"] and img.mode in ['RGB', 'RGBA']:
                        save_kwargs['compression'] = 1  # RLE compression
                
                case 'AVIF':
                    # AVIF quality settings
                    if settings["quality"] is not None:
                        save_kwargs['quality'] = min(max(1, settings["quality"]), 100)
                    else:
                        save_kwargs['quality'] = 75  # Default quality
                    
                    # AVIF encoder speed: 0-10 (slower = better quality)
                    save_kwargs['speed'] = settings["avif_speed"]
                
                case 'HEIF' | 'HEIC':
                    pil_format = 'HEIF'  # Standardize the format name
                    # HEIF quality settings
                    if settings["quality"] is not None:
                        save_kwargs['quality'] = settings["quality"]
                    else:
                        save_kwargs['quality'] = 80  # Default quality
                
                case 'ICO':
                    # ICO format has specific size requirements
                    # Resize to common icon sizes if larger than 256x256
                    if img.width > 256 or img.height > 256:
                        img.thumbnail((256, 256), Image.LANCZOS)
                        
                case 'TGA':
                    if settings["tga_compression"]:
                        save_kwargs['compression'] = "tga_rle"  # TGA Compression
                    
                case 'PPM' | 'PBM' | 'PNM' | 'PGM' | 'SGI':
                    pass  # No special settings needed
            
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