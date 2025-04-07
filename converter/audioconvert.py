import ffmpeg 
import tempfile
import os
import shutil
import subprocess
from loguru import logger

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
    format_lower = target_format.lower()
    
    # Ensure lossless is properly treated as boolean
    lossless = bool(lossless)
    
    # Format to codec mapping
    if format_lower == "mp3":
        return "libmp3lame"
    elif format_lower == "ogg":
        return "libvorbis"
    elif format_lower == "opus":
        return "libopus"
    elif format_lower in ["aac", "m4a"]:
        return "aac"
    elif format_lower == "flac":
        return "flac"
    elif format_lower == "alac":
        return "alac"
    elif format_lower in ["wav", "aiff"]:
        # Explicitly return a string codec name based on lossless boolean
        return "pcm_s24le" if lossless else "pcm_s16le"
    elif format_lower == "wma":
        return "wmav2"
    elif format_lower == "amr":
        return "libopencore_amrnb"
    elif format_lower == "ac3":
        return "ac3"
    
    # Default to a common codec if format is unknown
    return "libmp3lame"

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
    
    # Safeguard against 'False' or 'None' becoming the codec name
    if codec.lower() in ['false', 'none', 'true']:
        logger.warning(f"Invalid codec value: {codec}. Using default for {target_format}.")
        codec = get_default_codec_for_format(target_format, lossless=False)
        
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
            # Enhanced logging to debug issues
            logger.debug(f"Converting audio to {target_format} with codec {codec}")
            logger.debug(f"FFmpeg options: {output_options}")
            
            # Log the command we're about to execute
            print(f"Running FFmpeg: input={temp_input.name}, output={temp_output.name}, options={output_options}")
            
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
            raise RuntimeError(f"FFmpeg conversion failed: {str(e)}")

        # Read the result
        with open(temp_output.name, "rb") as f:
            result = f.read()

        return result
    except Exception as e:
        raise RuntimeError(f"Audio conversion failed: {str(e)}")
    finally:
        # Clean up temp files
        if temp_input and os.path.exists(temp_input.name):
            try:
                os.unlink(temp_input.name)
            except:
                pass
                
        if temp_output and os.path.exists(temp_output.name):
            try:
                os.unlink(temp_output.name)
            except:
                pass
