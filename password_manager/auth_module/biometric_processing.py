"""
Biometric data processing pipelines for MFA views.

Converts raw base64-decoded bytes into the numpy arrays expected by
BiometricAuthenticator:
  - Face images  → (160, 160, 3) float32, range [0, 1]
  - Voice audio  → (40, 100, 1) float32  (MFCC features)
"""

import io
import logging
import struct

import numpy as np

logger = logging.getLogger(__name__)

FACE_TARGET_SIZE = (160, 160)

# ---------------------------------------------------------------------------
# Face image processing
# ---------------------------------------------------------------------------

def decode_face_image(image_bytes: bytes) -> np.ndarray:
    """Decode raw image bytes into a (160, 160, 3) float32 numpy array.

    Uses OpenCV (headless) which is listed in requirements.txt.  Falls back
    to a minimal JPEG/PNG decode path when cv2 is unavailable.

    Raises ``ValueError`` if the image cannot be decoded.
    """
    try:
        import cv2

        buf = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)  # BGR uint8
        if img is None:
            raise ValueError("cv2.imdecode returned None — unsupported or corrupt image")

        img = cv2.resize(img, FACE_TARGET_SIZE, interpolation=cv2.INTER_AREA)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return (img.astype(np.float32) / 255.0)

    except ImportError:
        logger.warning("opencv-python-headless not installed; attempting PIL fallback")

    try:
        from PIL import Image

        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        pil_img = pil_img.resize(FACE_TARGET_SIZE, Image.LANCZOS)
        return np.asarray(pil_img, dtype=np.float32) / 255.0

    except ImportError:
        raise RuntimeError(
            "Neither opencv-python-headless nor Pillow is installed. "
            "Install at least one to process face images."
        )


# ---------------------------------------------------------------------------
# Voice audio processing
# ---------------------------------------------------------------------------

def _parse_wav_bytes(audio_bytes: bytes):
    """Return (sample_rate, samples_float32) from in-memory WAV data.

    Supports 16-bit PCM and 32-bit float WAV.  Falls back to
    ``scipy.io.wavfile`` when the simple parser cannot handle the format.
    """
    try:
        from scipy.io import wavfile

        sr, data = wavfile.read(io.BytesIO(audio_bytes))
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        elif data.dtype != np.float32:
            data = data.astype(np.float32)
        if data.ndim > 1:
            data = data.mean(axis=1)
        return sr, data

    except Exception:
        pass

    # Minimal manual WAV header parser (PCM-16 only)
    if audio_bytes[:4] != b"RIFF" or audio_bytes[8:12] != b"WAVE":
        raise ValueError("Audio data is not a valid WAV file")

    pos = 12
    sr = 16000
    sample_width = 2
    while pos < len(audio_bytes) - 8:
        chunk_id = audio_bytes[pos:pos + 4]
        chunk_size = struct.unpack_from("<I", audio_bytes, pos + 4)[0]
        if chunk_id == b"fmt ":
            sr = struct.unpack_from("<I", audio_bytes, pos + 12)[0]
            sample_width = struct.unpack_from("<H", audio_bytes, pos + 22)[0] // 8
        elif chunk_id == b"data":
            raw = audio_bytes[pos + 8:pos + 8 + chunk_size]
            if sample_width == 2:
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sample_width == 4:
                samples = np.frombuffer(raw, dtype=np.float32)
            else:
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            return sr, samples
        pos += 8 + chunk_size

    raise ValueError("Could not locate 'data' chunk in WAV file")


def _compute_mfcc_scipy(
    samples: np.ndarray,
    sample_rate: int,
    n_mfcc: int = 40,
    n_fft: int = 2048,
    hop_length: int = 512,
    n_mels: int = 128,
    target_frames: int = 100,
) -> np.ndarray:
    """Compute MFCCs using only numpy + scipy (no librosa dependency).

    Returns an array of shape ``(n_mfcc, target_frames, 1)``.
    """
    from scipy.fft import dct

    # Pre-emphasis
    emphasized = np.append(samples[0], samples[1:] - 0.97 * samples[:-1])

    # Framing
    num_samples = len(emphasized)
    frame_length = n_fft
    num_frames = 1 + (num_samples - frame_length) // hop_length
    if num_frames < 1:
        emphasized = np.pad(emphasized, (0, frame_length - num_samples))
        num_frames = 1

    indices = (
        np.arange(frame_length)[None, :]
        + np.arange(num_frames)[:, None] * hop_length
    )
    indices = np.clip(indices, 0, len(emphasized) - 1)
    frames = emphasized[indices]

    # Windowing
    window = np.hanning(frame_length)
    frames = frames * window

    # Power spectrum
    mag = np.abs(np.fft.rfft(frames, n=n_fft))
    power = (mag ** 2) / n_fft

    # Mel filter bank
    low_freq_mel = 0.0
    high_freq_mel = 2595.0 * np.log10(1.0 + (sample_rate / 2.0) / 700.0)
    mel_points = np.linspace(low_freq_mel, high_freq_mel, n_mels + 2)
    hz_points = 700.0 * (10.0 ** (mel_points / 2595.0) - 1.0)
    bin_points = np.floor((n_fft + 1) * hz_points / sample_rate).astype(int)

    fbank = np.zeros((n_mels, n_fft // 2 + 1))
    for m in range(1, n_mels + 1):
        f_left = bin_points[m - 1]
        f_center = bin_points[m]
        f_right = bin_points[m + 1]
        for k in range(f_left, f_center):
            if f_center != f_left:
                fbank[m - 1, k] = (k - f_left) / (f_center - f_left)
        for k in range(f_center, f_right):
            if f_right != f_center:
                fbank[m - 1, k] = (f_right - k) / (f_right - f_center)

    mel_spec = np.dot(power, fbank.T)
    mel_spec = np.where(mel_spec == 0, np.finfo(float).eps, mel_spec)
    log_mel = np.log(mel_spec)

    # DCT to get MFCCs
    mfccs = dct(log_mel, type=2, axis=1, norm="ortho")[:, :n_mfcc]
    mfccs = mfccs.T  # shape: (n_mfcc, num_frames)

    # Pad or truncate to target_frames
    if mfccs.shape[1] < target_frames:
        pad_width = ((0, 0), (0, target_frames - mfccs.shape[1]))
        mfccs = np.pad(mfccs, pad_width, mode="constant")
    else:
        mfccs = mfccs[:, :target_frames]

    return np.expand_dims(mfccs, axis=-1).astype(np.float32)


def decode_voice_audio(audio_bytes: bytes) -> np.ndarray:
    """Convert raw audio bytes (WAV) into MFCC features (40, 100, 1).

    Attempts to use ``librosa`` first (matching the BiometricAuthenticator
    pipeline).  Falls back to a scipy-based MFCC implementation.

    Raises ``ValueError`` if the audio cannot be parsed.
    """
    sr, samples = _parse_wav_bytes(audio_bytes)

    try:
        import librosa

        mfccs = librosa.feature.mfcc(
            y=samples, sr=sr, n_mfcc=40, n_fft=2048, hop_length=512
        )
        if mfccs.shape[1] < 100:
            mfccs = np.pad(mfccs, ((0, 0), (0, 100 - mfccs.shape[1])), mode="constant")
        else:
            mfccs = mfccs[:, :100]
        return np.expand_dims(mfccs, axis=-1).astype(np.float32)

    except ImportError:
        logger.info("librosa not available; using scipy-based MFCC extraction")

    return _compute_mfcc_scipy(samples, sr)
