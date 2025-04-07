# app/services/converters/video.py
import ffmpeg
import tempfile
import os

def convert_video(input_bytes: bytes, target_format: str, remove_metadata: bool = False, 
                  codec: str = None, crf: int = 23, preset: str = "fast", 
                  bitrate: str = None) -> bytes:
    """
    Convert video to target format with optional compression settings.
    
    Args:
        input_bytes: Input video as bytes
        target_format: Target format extension (mp4, webm, etc.)
        remove_metadata: Whether to strip metadata from output
        codec: Video codec to use for encoding (if None, uses format default)
            Common codecs:
                - H.264: "libx264" (works with: mp4, mkv, mov)
                - H.265/HEVC: "libx265" (works with: mp4, mkv)
                - VP9: "libvpx-vp9" (works with: webm)
                - VP8: "libvpx" (works with: webm)
                - AV1: "libaom-av1" (works with: mp4, mkv)
                - ProRes: "prores_ks" (works with: mov)
        crf: Constant Rate Factor for quality (lower = better quality)
            H.264: 18-28 (23 is default, visually lossless)
            H.265: 23-28 (28 is default)
            VP9: 15-35 (31 is default)
        preset: Compression speed/efficiency tradeoff
            Options: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
        bitrate: Target bitrate (e.g., "1M" for 1 Mbps)
    
    Returns:
        Converted video as bytes
        
    Supported formats:
        - mp4: Standard container format, works with H.264, H.265, AV1 codecs
        - webm: Google's container format, works best with VP8, VP9 codecs
        - mkv: Matroska container, supports virtually all codecs
        - mov: Apple QuickTime container, works with H.264 and ProRes
        - avi: Legacy container format, limited modern codec support
        - wmv: Windows Media Video format
        - flv: Flash Video format (legacy)
        - ts: MPEG Transport Stream
        - mts: AVCHD (Advanced Video Coding High Definition)
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".input") as temp_input:
        temp_input.write(input_bytes)
        temp_input.flush()

    output_path = tempfile.mktemp(suffix=f".{target_format}")

    # Build output options dictionary
    output_options = {}
    if remove_metadata:
        output_options["map_metadata"] = -1
    if codec is not None:
        output_options["c:v"] = codec
    if crf is not None:
        output_options["crf"] = str(crf)
    if preset is not None:
        output_options["preset"] = preset
    if bitrate is not None:
        output_options["b:v"] = bitrate

    ffmpeg_cmd = (
        ffmpeg
        .input(temp_input.name)
        .output(output_path, **output_options)
        .run_async(overwrite_output=True)
    )
    ffmpeg_cmd.wait()

    with open(output_path, "rb") as f:
        result = f.read()

    os.remove(temp_input.name)
    os.remove(output_path)

    return result
