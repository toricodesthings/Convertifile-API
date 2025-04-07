# Image Converter Module

from PIL import Image
import io
from loguru import logger

def convert_image(
    input_bytes: bytes, 
    target_format: str, 
    remove_metadata: bool = False,
    quality: int = None,
    optimize: bool = False,
    bmp_compression: bool = False,
) -> bytes:
    """
    Convert image to target format with optional compression and optimize settings.
    
    Parameters:
    -----------
    input_bytes : bytes
        The source image data as bytes
    target_format : str
        The target image format (e.g., 'jpg', 'png', 'webp')
    remove_metadata : bool, default=False
        Whether to strip metadata from the image
    quality : int, optional
        Quality level (1-100): higher value means better quality but larger file size
    optimize : bool, default=False
        Whether to optimize the image (format-dependent)
    bmp_compression : bool, default=False
        Whether to use RLE compression for BMP images
        
    Returns:
    --------
    bytes
        The converted image data as bytes
    """
    logger.info(f"Starting image conversion to {target_format}")
    
    try:
        with Image.open(io.BytesIO(input_bytes)) as img:
            output_io = io.BytesIO()

            save_kwargs = {}
            if remove_metadata:
                img.info = {}
            
            # Normalize target format for saving
            pil_format = target_format.upper()
            
            # Format-specific settings
            match pil_format:
                case 'JPEG':
                    # Handle RGBA to RGB conversion (JPEG doesn't support alpha channel)
                    if img.mode == 'RGBA':
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        # Paste the image using the alpha channel as mask
                        background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
                        img = background
                    
                    # JPEG quality: 1-100 (higher is better quality but larger file)
                    if quality is not None:
                        save_kwargs['quality'] = min(max(1, quality), 100)
                    else:
                        save_kwargs['quality'] = 100  # Default to max quality
                
                case 'WEBP':
                    # WebP quality: 1-100 (higher is better quality but larger file)
                    if quality is not None:
                        save_kwargs['quality'] = min(max(1, quality), 100)
                    else:
                        save_kwargs['quality'] = 100  # Default to max quality
                
                case 'PNG':
                    # PNG uses lossless compression
                    if optimize:
                        save_kwargs['optimize'] = True
                    if quality is not None:
                        # Convert quality (1-100) to compression level (0-9)
                        compression_level = max(0, min(9, 9 - (quality // 11)))
                        save_kwargs['compress_level'] = compression_level
                
                case 'TIFF':
                    # TIFF compression method selection based on quality
                    if quality is not None:
                        save_kwargs['compression'] = 'jpeg' if quality < 90 else 'lzw'
                
                case 'GIF':
                    if optimize:
                        save_kwargs['optimize'] = True
                
                case 'BMP':
                    if bmp_compression and img.mode in ['RGB', 'RGBA']:
                        save_kwargs['compression'] = 1  # RLE compression
            
            logger.info(f"Saving image with format {pil_format}, options: {save_kwargs}")
            img.save(output_io, format=pil_format, **save_kwargs)
            output_io.seek(0) # Reset stream position to the beginning
            return output_io.read()
            
    except Exception as e:
        logger.error(f"Image conversion error: {str(e)}", exc_info=True)
        raise ValueError(f"Image conversion failed: {str(e)}")