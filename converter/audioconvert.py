import ffmpeg, tempfile, os, subprocess, logging
from loguru import logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("audioconv.log"),
        logging.StreamHandler()
    ]
)

logger.configure(
    handlers=[
        {"sink": "audioconv.log", "rotation": "10 MB", "retention": "1 day"},
        {"sink": lambda msg: print(msg, end=""), "level": "INFO"}
    ]
)

# Check if ffmpeg is available in PATH
def is_ffmpeg_available():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

def get_default_codec_for_format(target_format: str, lossless: bool = False) -> str:
    """
    Determine the appropriate codec based on target format.
    
    Args:
        target_format: Target format extension (mp3, flac, etc.)
        lossless: If True and target format supports it, use lossless encoding
    
    Returns:
        Appropriate codec name for the given format
    """
    
    # Ensure lossless is properly treated as boolean
    lossless = bool(lossless)
    
    # Format to codec mapping
    match target_format:
        case "mp3":
            return "libmp3lame"
        case "ogg":
            return "libvorbis"
        case "opus":
            return "libopus"
        case "aac" | "m4a":
            return "aac"
        case "flac":
            return "flac"
        case "alac":
            return "alac"
        case "wav" | "aiff":
            return "pcm_s24le" if lossless else "pcm_s16le"
        case "wma":
            return "wmav2"
        case "amr":
            return "libopencore_amrnb"
        case "ac3":
            return "ac3"
        case _:
            return "libmp3lame"
        
    # Default to a common codec if format is unknown
    return "libmp3lame"

def validate_format_codec_compatibility(target_format: str, codec: str) -> bool:
    """
    Validates if the codec is compatible with the target format.
    
    Args:
        target_format: Target format extension
        codec: Audio codec
    
    Returns:
        True if compatible, False otherwise
    """
    format_codec_map = {
        "mp3": ["libmp3lame"],
        "ogg": ["libvorbis", "libopus"],
        "opus": ["libopus"],
        "aac": ["aac"],
        "m4a": ["aac", "alac"],
        "flac": ["flac"],
        "alac": ["alac"],
        "wav": ["pcm_s16le", "pcm_s24le", "pcm_f32le"],
        "aiff": ["pcm_s16le", "pcm_s24le"],
        "wma": ["wmav2"],
        "amr": ["libopencore_amrnb"],
        "ac3": ["ac3"]
    }
    
    # If format isn't in our map, we'll assume compatibility
    if target_format not in format_codec_map:
        logger.warning(f"Format '{target_format}' is not in our compatibility database")
        return True
    
    compatible = codec in format_codec_map[target_format]
    if not compatible:
        logger.warning(f"Codec '{codec}' may not be compatible with format '{target_format}'")
    
    return compatible

def convert_audio(input_bytes: bytes, target_format: str, remove_metadata: bool = False,
                 codec: str = None, bitrate: str = None, sample_rate: int = None,
                 channels: int = None, quality: int = None, lossless: bool = False) -> bytes:
    """
    Convert audio to target format with optional quality settings.
    
    Args:
        input_bytes: Input audio as bytes
        target_format: Target format extension (mp3, flac, etc.)
        remove_metadata: Whether to strip metadata from output
        codec: Audio codec to use for encoding (if None, uses format default)
            Common codecs:
                - MP3: "libmp3lame" (lossy)
                - AAC: "aac" (lossy)
                - Opus: "libopus" (lossy)
                - FLAC: "flac" (lossless)
                - ALAC: "alac" (lossless)
                - Vorbis: "libvorbis" (lossy)
                - PCM: "pcm_s16le", "pcm_s24le" (lossless)
                - WavPack: "wavpack" (lossless)
        bitrate: Target bitrate (e.g., "192k" for 192 kbps)
        sample_rate: Output sample rate in Hz (e.g., 44100, 48000)
        channels: Number of audio channels (1=mono, 2=stereo)
        quality: Quality setting (codec-specific, typically 0-9 where lower is better)
        lossless: If True and target format supports it, use lossless encoding
    
    Returns:
        Converted audio as bytes
        
    Supported formats:
        - mp3: Most common lossy format, good compatibility (codec: libmp3lame)
        - ogg: Ogg container with Vorbis codec (codec: libvorbis)
        - opus: High efficiency lossy codec in Ogg container (codec: libopus)
        - flac: Free Lossless Audio Codec (codec: flac)
        - wav: Waveform Audio, typically uncompressed PCM
        - aac: Advanced Audio Coding, lossy compression
        - m4a: AAC audio in MPEG-4 container
        - alac: Apple Lossless Audio Codec
        - wma: Windows Media Audio
        - aiff: Audio Interchange File Format, lossless
        - amr: Adaptive Multi-Rate, speech-optimized format
        - ac3: Dolby Digital audio format
    """
    
    target_format = target_format.lower()
    
    # First, check if FFmpeg is available
    if not is_ffmpeg_available():
        raise RuntimeError("FFmpeg is not installed or not available in your PATH. Please install FFmpeg and make sure it's in your system PATH.")
    
    # Ensure we have a valid codec based on target format
    if codec is None:
        codec = get_default_codec_for_format(target_format, lossless)
    
    # Ensure codec is a string, not a boolean or other type
    if not isinstance(codec, str):
        logger.warning(f"Invalid codec type: {type(codec)}. Converting to string.")
        codec = str(codec)
    
    # Validate codec compatibility with format
    validate_format_codec_compatibility(target_format, codec)
        
    # Check for lossless incompatibility
    if lossless and target_format not in ['flac', 'alac', 'wav', 'aiff']:
        logger.warning(f"Lossless encoding requested but format '{target_format}' is typically lossy, proceeding...")

    if lossless and (bitrate is not None or quality is not None):
        bitrate = None
        quality = None
        logger.warning(f"Bitrate settings are ignored for lossless encoding")
        
    
    temp_input = None
    temp_output = None
    
    try:
        # Create input temp file
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".input")
        temp_input.write(input_bytes)
        temp_input.flush()
        temp_input.close()  # Close the file to ensure it's accessible to ffmpeg
        
        # Verify input file exists and has content
        if not os.path.exists(temp_input.name) or os.path.getsize(temp_input.name) == 0:
            raise RuntimeError(f"Input file creation failed: {temp_input.name}")
        
        # Create output temp file
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=f".{target_format}")
        temp_output.close()  # Close the file but keep the name for ffmpeg to write to
        
        # Build output options dictionary
        output_options = {}
        if remove_metadata:
            output_options["map_metadata"] = -1
            
        # Set the codec - with additional logging
        logger.debug(f"Using codec: '{codec}' for format: {target_format}")
        output_options["c:a"] = codec
                
        # Audio-specific parameters
        if bitrate is not None and not lossless:
            output_options["b:a"] = bitrate
        if sample_rate is not None:
            output_options["ar"] = str(sample_rate)
        if channels is not None:
            output_options["ac"] = str(channels)
        if quality is not None and not bitrate and not lossless:
            # Quality setting varies by codec
            if codec == "libmp3lame":
                # MP3 quality: 0 (best) to 9 (worst)
                output_options["q:a"] = str(quality)
            elif codec == "libvorbis":
                # Vorbis quality: 0-10 (higher is better)
                output_options["q:a"] = str(quality)
                
        try:
            logger.info(f"Converting audio to {target_format} with codec {codec}")
            logger.info(f"FFmpeg options: {output_options}")
            
            # Generate debug log with equivalent FFmpeg command
            cmd_str = f"ffmpeg -i {temp_input.name} "
            for key, value in output_options.items():
                cmd_str += f"-{key} {value} "
            cmd_str += temp_output.name
            logger.debug(f"Equivalent FFmpeg command: {cmd_str}")
            
            # Log the command we're about to execute
            logger.info(f"Running FFmpeg: input={temp_input.name}, output={temp_output.name}, options={output_options}")
            
            ffmpeg_cmd = (
                ffmpeg
                .input(temp_input.name)
                .output(temp_output.name, **output_options)
                .run_async(overwrite_output=True)
            )
            ffmpeg_cmd.wait()
            
            # Verify output file was created
            if not os.path.exists(temp_output.name):
                raise RuntimeError(f"Output file was not created: {temp_output.name}")
            
            if os.path.getsize(temp_output.name) == 0:
                raise RuntimeError(f"Output file is empty: {temp_output.name}")
                
        except Exception as e:
            # Capture FFmpeg error output when available
            stderr_msg = ""
            try:
                if hasattr(ffmpeg_cmd, 'stderr'):
                    stderr_msg = ffmpeg_cmd.stderr.read().decode('utf-8', errors='replace')
                    logger.error(f"FFmpeg stderr: {stderr_msg}")
            except:
                pass
            
            raise RuntimeError(f"FFmpeg conversion failed: {str(e)}{' - ' + stderr_msg if stderr_msg else ''}")

        # Read the result
        with open(temp_output.name, "rb") as f:
            return f.read()

    except Exception as e:
        logger.error(f"Audio conversion failed: {str(e)}")
        raise RuntimeError(f"Audio conversion failed: {str(e)}")
    finally:
        # Clean up temp files with better error handling
        for temp_file in [temp_input, temp_output]:
            if temp_file and hasattr(temp_file, 'name') and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                    logger.debug(f"Successfully removed temp file: {temp_file.name}")
                except Exception as ex:
                    logger.warning(f"Failed to remove temp file {temp_file.name}: {str(ex)}")
