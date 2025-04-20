import os
import tempfile
import subprocess
import logging

import ffmpeg
from loguru import logger

# Ensure logs directory exists and use it for logging
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "videoconv.log")

logger.configure(
    handlers=[
        {"sink": LOG_FILE, "rotation": "10 MB", "retention": "1 day"},
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

def build_output_options(settings):
    """Build ffmpeg output options dict from settings dict."""
    options = {}
    codec = settings.get("codec")
    remove_metadata = settings.get("remove_metadata", False)
    crf = settings.get("crf")
    speed = settings.get("speed")
    bitrate = settings.get("bitrate")
    fps = settings.get("fps")
    profile = settings.get("profile")
    level = settings.get("level")

    if remove_metadata:
        options["map_metadata"] = -1
    if codec:
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

# --- Main Conversion Function ---

def convert_video(
    input_bytes: bytes,
    target_format: str,
    settings: dict = None
) -> bytes:
    """
    Convert video to target format with optional compression settings.
    Args:
        input_bytes: Input video as bytes
        target_format: Target format extension (mp4, webm, etc.)
        settings: Dictionary of optional settings:
            remove_metadata: Whether to strip metadata from output
            codec: Video codec to use for encoding (if None, uses format default)
            crf: Constant Rate Factor for quality (lower = better quality)
            profile: Codec profile
            level: Codec level
            speed: Compression speed/efficiency tradeoff
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

    settings = settings or {}

    codec = settings.get("codec") or get_default_codec_for_format(target_format)
    validate_format_codec_compatibility(target_format, codec)
    profile, level = get_codec_profile_level(
        codec,
        settings.get("profile"),
        settings.get("level")
    )
    # Ensure codec, profile, and level are set in settings for build_output_options
    settings["codec"] = codec
    settings["profile"] = profile
    settings["level"] = level

    output_options = build_output_options(settings)

    logger.debug(f"Using codec: '{codec}' for format: {target_format}")
    logger.info(f"Converting video to {target_format} with codec {codec}")
    logger.info(f"FFmpeg options: {output_options}")

    # Log equivalent ffmpeg command
    cmd_str = f"ffmpeg -i pipe:0 "
    for key, value in output_options.items():
        cmd_str += f"-{key} {value} "
    cmd_str += "-f " + target_format + " pipe:1"
    logger.debug(f"Equivalent FFmpeg command: {cmd_str}")

    logger.info(f"Running FFmpeg in-memory (pipe) for conversion to {target_format}")

    try:
        stream = ffmpeg.input('pipe:0')
        stream = stream.output('pipe:1', format=target_format, **output_options).overwrite_output()
        out, err = stream.run(input=input_bytes, capture_stdout=True, capture_stderr=True, quiet=True)
        if not out or len(out) == 0:
            logger.error(f"Output from ffmpeg is empty. Stderr: {err.decode(errors='ignore')}")
            raise RuntimeError("Output from ffmpeg is empty.")
        return out
    except Exception as e:
        logger.warning(f"In-memory conversion failed, falling back to temp files. Reason: {str(e)}")
        # Fallback to temp files if in-memory fails
        temp_input = temp_output = None
        try:
            temp_input = create_temp_file(".input", input_bytes)
            if not os.path.exists(temp_input.name) or os.path.getsize(temp_input.name) == 0:
                raise RuntimeError(f"Input file creation failed: {temp_input.name}")

            temp_output = create_temp_file(f".{target_format}")
            # Use updated settings for build_output_options
            output_options = build_output_options(settings)

            logger.debug(f"Using codec: '{codec}' for format: {target_format}")
            logger.info(f"Converting video to {target_format} with codec {codec}")
            logger.info(f"FFmpeg options: {output_options}")

            # Log equivalent ffmpeg command
            cmd_str = f"ffmpeg -i {temp_input.name} "
            for key, value in output_options.items():
                cmd_str += f"-{key} {value} "
            cmd_str += temp_output.name
            logger.debug(f"Equivalent FFmpeg command: {cmd_str}")

            logger.info(f"Running FFmpeg: input={temp_input.name}, output={temp_output.name}, options={output_options}")

            # Run ffmpeg
            stream = ffmpeg.input(temp_input.name)
            stream = stream.output(temp_output.name, **output_options).overwrite_output()
            stream.run(quiet=True)

            if not os.path.exists(temp_output.name):
                raise RuntimeError(f"Output file was not created: {temp_output.name}")
            if os.path.getsize(temp_output.name) == 0:
                raise RuntimeError(f"Output file is empty: {temp_output.name}")

            with open(temp_output.name, "rb") as f:
                return f.read()
        except Exception as e2:
            logger.error(f"Video conversion failed: {str(e2)}")
            raise RuntimeError(f"Video conversion failed: {str(e2)}")
        finally:
            cleanup_temp_files(temp_input, temp_output)
