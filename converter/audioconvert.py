import os
import tempfile
import subprocess
import logging

import ffmpeg
from loguru import logger

# --- Logging Configuration ---
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

# --- Utility Functions ---

def is_ffmpeg_available() -> bool:
    """Check if ffmpeg is available in the system PATH."""
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

def get_default_codec_for_format(target_format: str, lossless: bool = False) -> str:
    """
    Return the default codec for a given target format.
    """
    target_format = target_format.lower()
    lossless = bool(lossless)
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

def validate_format_codec_compatibility(target_format: str, codec: str) -> bool:
    """
    Validate if the codec is compatible with the target format.
    """
    format_codec_map = {
        "mp3": ["libmp3lame"],
        "ogg": ["libvorbis", "libopus"],
        "opus": ["libopus"],
        "aac": ["aac"],
        "m4a": ["aac"],
        "flac": ["flac"],
        "alac": ["alac"],
        "wav": ["pcm_s16le", "pcm_s24le", "pcm_f32le"],
        "aiff": ["pcm_s16le", "pcm_s24le"],
        "wma": ["wmav2"],
        "amr": ["libopencore_amrnb"],
        "ac3": ["ac3"]
    }
    if target_format not in format_codec_map:
        logger.warning(f"Format '{target_format}' is not in the compatibility database")
        return True
    compatible = codec in format_codec_map[target_format]
    if not compatible:
        logger.warning(f"Codec '{codec}' may not be compatible with format '{target_format}'")
    return compatible

# --- Main Conversion Function ---

def convert_audio(
    input_bytes: bytes,
    target_format: str,
    remove_metadata: bool = False,
    codec: str = None,
    bitrate: str = None,
    sample_rate: int = None,
    channels: int = 2,
    lossless: bool = False,
    compression_level: int = None
) -> bytes:
    """
    Convert audio to a target format with optional quality settings.

    Args:
        input_bytes: Input audio as bytes.
        target_format: Target format extension (e.g., mp3, flac).
        remove_metadata: Strip metadata from output.
        codec: Audio codec for encoding (default: format's standard).
        bitrate: Target bitrate (e.g., "192k").
        sample_rate: Output sample rate in Hz.
        channels: Number of audio channels.
        lossless: Use lossless encoding if supported.
        compression_level: Compression level for supported codecs.

    Returns:
        Converted audio as bytes.
    """
    target_format = target_format.lower()

    # Automatically enable lossless for certain formats
    if target_format in {'flac', 'alac', 'wav', 'aiff'}:
        lossless = True
    else:
        lossless = False

    if not is_ffmpeg_available():
        raise RuntimeError("FFmpeg is not installed or not available in your PATH. Please install FFmpeg and make sure it's in your system PATH.")

    # Determine codec
    if codec is None:
        codec = get_default_codec_for_format(target_format, lossless)
    if not isinstance(codec, str):
        logger.warning(f"Invalid codec type: {type(codec)}. Converting to string.")
        codec = str(codec)

    validate_format_codec_compatibility(target_format, codec)

    if lossless and bitrate is not None:
        bitrate = None

    temp_input = None
    temp_output = None

    try:
        # --- Write input bytes to temp file ---
        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".input")
        temp_input.write(input_bytes)
        temp_input.flush()
        temp_input.close()

        if not os.path.exists(temp_input.name) or os.path.getsize(temp_input.name) == 0:
            raise RuntimeError(f"Input file creation failed: {temp_input.name}")

        # --- Prepare output temp file ---
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=f".{target_format}")
        temp_output.close()

        # --- Build ffmpeg output options ---
        output_options = {}
        if remove_metadata:
            output_options["map_metadata"] = -1
        output_options["c:a"] = codec

        if bitrate is not None and not lossless:
            output_options["b:a"] = bitrate
        if sample_rate is not None:
            output_options["ar"] = str(sample_rate)
        if compression_level is not None and str(codec).lower() in {"flac", "libmp3lame", "libopus"}:
            output_options["compression_level"] = compression_level
        output_options["ac"] = str(channels)

        logger.debug(f"Using codec: '{codec}' for format: {target_format}")
        logger.info(f"Converting audio to {target_format} with codec {codec}")
        logger.info(f"FFmpeg options: {output_options}")

        # --- Log equivalent ffmpeg command ---
        cmd_str = f"ffmpeg -i {temp_input.name} "
        for key, value in output_options.items():
            cmd_str += f"-{key} {value} "
        cmd_str += temp_output.name
        logger.debug(f"Equivalent FFmpeg command: {cmd_str}")

        logger.info(f"Running FFmpeg: input={temp_input.name}, output={temp_output.name}, options={output_options}")

        # --- Run ffmpeg ---
        ffmpeg_cmd = (
            ffmpeg
            .input(temp_input.name)
            .output(temp_output.name, **output_options)
            .run_async(overwrite_output=True)
        )
        ffmpeg_cmd.wait()

        if not os.path.exists(temp_output.name):
            raise RuntimeError(f"Output file was not created: {temp_output.name}")
        if os.path.getsize(temp_output.name) == 0:
            raise RuntimeError(f"Output file is empty: {temp_output.name}")

        # --- Read and return result ---
        with open(temp_output.name, "rb") as f:
            return f.read()

    except Exception as e:
        logger.error(f"Audio conversion failed: {str(e)}")
        raise RuntimeError(f"Audio conversion failed: {str(e)}")
    finally:
        # --- Clean up temp files ---
        for temp_file in [temp_input, temp_output]:
            if temp_file and hasattr(temp_file, 'name') and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                    logger.debug(f"Successfully removed temp file: {temp_file.name}")
                except Exception as ex:
                    logger.warning(f"Failed to remove temp file {temp_file.name}: {str(ex)}")
