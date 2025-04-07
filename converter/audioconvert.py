import ffmpeg
import tempfile
import os

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
    with tempfile.NamedTemporaryFile(delete=False, suffix=".input") as temp_input:
        temp_input.write(input_bytes)
        temp_input.flush()

    output_path = tempfile.mktemp(suffix=f".{target_format}")

    # Build output options dictionary
    output_options = {}
    if remove_metadata:
        output_options["map_metadata"] = -1
        
    # Handle codec selection
    if codec is not None:
        output_options["c:a"] = codec
    elif lossless and target_format.lower() in ["flac", "wav", "alac", "aiff"]:
        # Select appropriate lossless codec based on format
        if target_format.lower() == "flac":
            output_options["c:a"] = "flac"
        elif target_format.lower() == "alac":
            output_options["c:a"] = "alac"
        elif target_format.lower() in ["wav", "aiff"]:
            output_options["c:a"] = "pcm_s24le"  # 24-bit PCM for high quality
            
    # Audio-specific parameters
    if bitrate is not None and not lossless:
        output_options["b:a"] = bitrate
    if sample_rate is not None:
        output_options["ar"] = str(sample_rate)
    if channels is not None:
        output_options["ac"] = str(channels)
    if quality is not None and not bitrate and not lossless:
        # Quality setting varies by codec
        if (codec == "libmp3lame" or 
            (codec is None and target_format.lower() == "mp3")):
            # MP3 quality: 0 (best) to 9 (worst)
            output_options["q:a"] = str(quality)
        elif (codec == "libvorbis" or 
              (codec is None and target_format.lower() == "ogg")):
            # Vorbis quality: 0-10 (higher is better)
            output_options["q:a"] = str(quality)

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
