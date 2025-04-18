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
        logging.FileHandler("videoconv.log"),
        logging.StreamHandler()
    ]
)

logger.configure(
    handlers=[
        {"sink": "videoconv.log", "rotation": "10 MB", "retention": "1 day"},
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

def get_default_codec_for_format(target_format: str) -> str:
    """Return the default video codec for a given target format."""
    target_format = target_format.lower()
    match target_format:
        case "mp4" | "mov":
            return "libx264"
        case "webm":
            return "libvpx-vp9"
        case "mkv":
            return "libx264"
        case "avi":
            return "mpeg4"
        case "wmv":
            return "wmv2"
        case "flv":
            return "flv"
        case "ts" | "mts":
            return "libx264"
        case _:
            return "libx264"

def validate_format_codec_compatibility(target_format: str, codec: str) -> bool:
    """Validate if the codec is compatible with the target format."""
    format_codec_map = {
        "mp4": ["libx264", "libx265", "libaom-av1"],
        "webm": ["libvpx", "libvpx-vp9"],
        "mkv": ["libx264", "libx265", "libaom-av1", "libvpx-vp9"],
        "mov": ["libx264", "libx265"],
        "avi": ["mpeg4"],
        "wmv": ["wmv2"],
        "flv": ["flv", "libx264", "libx265"],
        "ts": ["libx264", "libx265"],
        "mts": ["libx264", "libx265"]
    }
    if target_format not in format_codec_map:
        logger.warning(f"Format '{target_format}' is not in the compatibility database")
        return True
    compatible = codec in format_codec_map[target_format]
    if not compatible:
        logger.warning(f"Codec '{codec}' may not be compatible with format '{target_format}'")
    return compatible

def create_temp_file(suffix: str, data: bytes = None) -> tempfile.NamedTemporaryFile:
    """Create a temp file, optionally writing data to it."""
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    if data is not None:
        temp.write(data)
        temp.flush()
    temp.close()
    return temp

def cleanup_temp_files(*files):
    """Remove temp files if they exist."""
    for temp_file in files:
        if temp_file and hasattr(temp_file, 'name') and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
                logger.debug(f"Successfully removed temp file: {temp_file.name}")
            except Exception as ex:
                logger.warning(f"Failed to remove temp file {temp_file.name}: {str(ex)}")

def get_codec_profile_level(codec, profile, level):
    """Return profile and level defaults for supported codecs."""
    defaults = {
        "libx264": ("high", "4.1"),
        "libx265": ("main", "4.1"),
        "libaom-av1": ("main", "4.0")
    }
    if codec in defaults:
        default_profile, default_level = defaults[codec]
        return profile or default_profile, level or default_level
    return profile, level

def build_output_options(codec, remove_metadata, crf, speed, bitrate, fps, profile, level):
    """Build ffmpeg output options dict."""
    options = {}
    if remove_metadata:
        options["map_metadata"] = -1
    options["c:v"] = codec
    if crf is not None:
        options["crf"] = str(crf)
    if speed is not None:
        options["preset"] = speed
    if bitrate is not None:
        options["b:v"] = bitrate
    if fps is not None:
        options["r"] = str(fps)
    if codec in ("libx264", "libx265", "libaom-av1"):
        if profile is not None:
            options["profile:v"] = profile
        if level is not None:
            options["level"] = level
    return options

def build_filters(width, height):
    """Build ffmpeg filter list for scaling."""
    if width is not None or height is not None:
        scale_expr = f"scale={width if width else -1}:{height if height else -1}"
        return [scale_expr]
    return []

# --- Main Conversion Function ---

def convert_video(
    input_bytes: bytes,
    target_format: str,
    remove_metadata: bool = False,
    codec: str = None,
    crf: int = None,
    profile: str = None,
    level: str = None,
    speed: str = None,
    bitrate: str = None,
    width: int = None,
    height: int = None,
    fps: int = None
) -> bytes:
    """
    Convert video to target format with optional compression settings.
    Args:
        input_bytes: Input video as bytes
        target_format: Target format extension (mp4, webm, etc.)
        remove_metadata: Whether to strip metadata from output
        codec: Video codec to use for encoding (if None, uses format default)
        crf: Constant Rate Factor for quality (lower = better quality)
        preset: Compression speed/efficiency tradeoff
        bitrate: Target bitrate (e.g., "1M" for 1 Mbps)
        width: Output width (optional)
        height: Output height (optional)
        fps: Output frames per second (optional)
    Returns:
        Converted video as bytes
    """
    target_format = target_format.lower()
    if not is_ffmpeg_available():
        raise RuntimeError("FFmpeg is not installed or not available in your PATH. Please install FFmpeg and make sure it's in your system PATH.")

    codec = codec or get_default_codec_for_format(target_format)
    validate_format_codec_compatibility(target_format, codec)
    profile, level = get_codec_profile_level(codec, profile, level)
    temp_input = temp_output = None

    try:
        temp_input = create_temp_file(".input", input_bytes)
        if not os.path.exists(temp_input.name) or os.path.getsize(temp_input.name) == 0:
            raise RuntimeError(f"Input file creation failed: {temp_input.name}")

        temp_output = create_temp_file(f".{target_format}")
        output_options = build_output_options(codec, remove_metadata, crf, speed, bitrate, fps, profile, level)
        filters = build_filters(width, height)

        logger.debug(f"Using codec: '{codec}' for format: {target_format}")
        logger.info(f"Converting video to {target_format} with codec {codec}")
        logger.info(f"FFmpeg options: {output_options}")

        # Log equivalent ffmpeg command
        cmd_str = f"ffmpeg -i {temp_input.name} "
        for key, value in output_options.items():
            cmd_str += f"-{key} {value} "
        if filters:
            cmd_str += f'-vf "{",".join(filters)}" '
        cmd_str += temp_output.name
        logger.debug(f"Equivalent FFmpeg command: {cmd_str}")

        logger.info(f"Running FFmpeg: input={temp_input.name}, output={temp_output.name}, options={output_options}")

        # Run ffmpeg
        stream = ffmpeg.input(temp_input.name)
        if filters:
            stream = stream.filter('scale', width if width else -1, height if height else -1)
        stream = stream.output(temp_output.name, **output_options).overwrite_output()
        stream.run(quiet=True)

        if not os.path.exists(temp_output.name):
            raise RuntimeError(f"Output file was not created: {temp_output.name}")
        if os.path.getsize(temp_output.name) == 0:
            raise RuntimeError(f"Output file is empty: {temp_output.name}")

        with open(temp_output.name, "rb") as f:
            return f.read()

    except Exception as e:
        logger.error(f"Video conversion failed: {str(e)}")
        raise RuntimeError(f"Video conversion failed: {str(e)}")
    finally:
        cleanup_temp_files(temp_input, temp_output)
