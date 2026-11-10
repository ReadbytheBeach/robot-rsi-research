#!/usr/bin/env python3
"""Educational constant-offset audio alignment for two Specialist-style recordings.

This original example is not Specialist's .insv parser or production synchronizer.
Dependencies: numpy, scipy; optional matplotlib for --plot.

Extract PCM audio without independently trimming either source first, for example:
    ffmpeg -i left.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le left.wav
    ffmpeg -i right.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le right.wav
    python audio_align.py left.wav right.wav --max-offset 5 --plot sync.png
    python audio_align.py --self-test

Timestamp convention matches the official synchronizer:
    t_right = t_left + offset_seconds
Therefore convert a right timestamp to the left timeline by subtracting offset.
A positive offset means a common event appears later in the right file.
The optional crop plan assumes each WAV starts at its video's time zero. Container
PTS, codec delays, clock drift and acoustic propagation require separate checks.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, correlate, correlation_lags, resample_poly, sosfiltfilt

AUDIO_RATE = 16_000
ENVELOPE_RATE = 1_000


class AlignmentError(ValueError):
    """The recordings do not provide a sufficiently unambiguous constant offset."""


def read_wav(path: Path) -> np.ndarray:
    """Read a PCM/float WAV, normalize integer ranges and resample to 16 kHz."""
    rate, raw = wavfile.read(path)
    if rate <= 0 or raw.size == 0:
        raise AlignmentError(f"Empty or invalid WAV: {path}")
    if np.issubdtype(raw.dtype, np.unsignedinteger):
        midpoint = (np.iinfo(raw.dtype).max + 1) / 2
        samples = (raw.astype(np.float64) - midpoint) / midpoint
    elif np.issubdtype(raw.dtype, np.signedinteger):
        samples = raw.astype(np.float64) / float(-np.iinfo(raw.dtype).min)
    elif np.issubdtype(raw.dtype, np.floating):
        samples = raw.astype(np.float64)
    else:
        raise AlignmentError(f"Unsupported WAV sample type: {raw.dtype}")
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    if samples.ndim != 1 or not np.isfinite(samples).all():
        raise AlignmentError("Audio must be finite mono/stereo PCM samples")
    samples -= samples.mean()
    if np.sqrt(np.mean(samples**2)) < 1e-6:
        raise AlignmentError("Silent or near-silent recording")
    divisor = math.gcd(int(rate), AUDIO_RATE)
    return resample_poly(samples, AUDIO_RATE // divisor, int(rate) // divisor)


def envelope(samples: np.ndarray) -> np.ndarray:
    """Rectify and low-pass at 50 Hz, then anti-alias downsample to 1 kHz."""
    if len(samples) < AUDIO_RATE // 2:
        raise AlignmentError("Audio is shorter than 0.5 seconds")
    filt = butter(4, 50.0, fs=AUDIO_RATE, output="sos")
    env = resample_poly(sosfiltfilt(filt, np.abs(samples)), 1, 16)
    if np.std(env) <= max(1e-10, 1e-4 * np.mean(np.abs(env))):
        raise AlignmentError("Audio envelope has insufficient variation")
    return env


def normalized_correlation(left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Overlap-wise Pearson correlation, with lag = right_time - left_time.

    Prefix sums remove each overlap's mean and normalize gain/overlap length.
    This differs from the official implementation's global-mean correlation.
    """
    lags = correlation_lags(len(right), len(left), mode="full")
    products = correlate(right, left, mode="full", method="fft")
    right_start = np.maximum(lags, 0)
    right_end = np.minimum(len(right), len(left) + lags)
    left_start = np.maximum(-lags, 0)
    left_end = np.minimum(len(left), len(right) - lags)
    count = right_end - right_start

    def sums(data: np.ndarray, begin: np.ndarray, end: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        prefix = np.r_[0.0, np.cumsum(data)]
        squared = np.r_[0.0, np.cumsum(data * data)]
        return prefix[end] - prefix[begin], squared[end] - squared[begin]

    sum_r, sq_r = sums(right, right_start, right_end)
    sum_l, sq_l = sums(left, left_start, left_end)
    numerator = products - sum_r * sum_l / count
    variance_r = np.maximum(0.0, sq_r - sum_r**2 / count)
    variance_l = np.maximum(0.0, sq_l - sum_l**2 / count)
    denominator = np.sqrt(variance_r * variance_l)
    corr = np.full_like(products, -np.inf)
    valid = denominator > 1e-14
    corr[valid] = np.clip(numerator[valid] / denominator[valid], -1.0, 1.0)
    return lags / ENVELOPE_RATE, corr, count / ENVELOPE_RATE


def estimate_offset(
    left: np.ndarray,
    right: np.ndarray,
    *,
    max_offset: float = 30.0,
    min_overlap: float = 2.0,
    min_correlation: float = 0.5,
    min_peak_ratio: float = 1.3,
    lobe_half_width: float = 0.25,
) -> dict:
    """Estimate one constant offset; reject weak, periodic or boundary peaks."""
    if not all(np.isfinite(x) and x > 0 for x in (max_offset, min_overlap, min_peak_ratio, lobe_half_width)):
        raise AlignmentError("Offset, overlap, peak ratio and lobe width must be positive")
    if not 0 < min_correlation <= 1 or min_peak_ratio <= 1:
        raise AlignmentError("Correlation must be in (0, 1]; peak ratio must exceed 1")
    env_l, env_r = envelope(left), envelope(right)
    offsets, corr, overlap = normalized_correlation(env_l, env_r)
    # Short intersections are easy to match accidentally. Require at least half
    # of the shorter recording, in addition to the caller's absolute minimum.
    required = max(min_overlap, 0.5 * min(len(env_l), len(env_r)) / ENVELOPE_RATE)
    allowed = (np.abs(offsets) <= max_offset) & (overlap >= required)
    candidates = np.where(allowed, corr, -np.inf)
    if not np.isfinite(candidates).any():
        raise AlignmentError("No candidate has enough overlapping audio")
    peak = int(np.argmax(candidates))
    height = float(candidates[peak])
    if height < min_correlation:
        raise AlignmentError(f"Weak audio match: correlation {height:.3f} < {min_correlation:.3f}")
    if peak == 0 or peak == len(corr) - 1 or not (allowed[peak - 1] and allowed[peak + 1]):
        raise AlignmentError("Best offset is at the search/overlap boundary; inspect the recordings")
    rivals = np.where(allowed & (np.abs(offsets - offsets[peak]) > lobe_half_width), corr, -np.inf)
    best_rival = float(np.max(rivals))
    ratio = height / best_rival if best_rival > 0 else math.inf
    if ratio < min_peak_ratio:
        raise AlignmentError(f"Ambiguous audio match: peak ratio {ratio:.3f} < {min_peak_ratio:.3f}")
    # Three-point parabolic interpolation gives a sub-grid estimate, not a
    # guarantee of sub-millisecond physical synchronization accuracy.
    y0, y1, y2 = corr[peak - 1 : peak + 2]
    curvature = y0 - 2 * y1 + y2
    substep = float(np.clip(0.5 * (y0 - y2) / curvature, -0.5, 0.5)) if curvature < 0 else 0.0
    offset = float(offsets[peak] + substep / ENVELOPE_RATE)
    duration_l, duration_r = len(left) / AUDIO_RATE, len(right) / AUDIO_RATE
    start_l = max(0.0, -offset)
    end_l = min(duration_l, duration_r - offset)
    return {
        "status": "accepted",
        "convention": "t_right = t_left + offset_seconds",
        "offset_seconds": offset,
        "right_to_left": "t_left = t_right - offset_seconds",
        "correlation": height,
        "peak_ratio": ratio if math.isfinite(ratio) else None,
        "peak_ratio_note": "null means no positive competing peak" if not math.isfinite(ratio) else "larger is less ambiguous; not a calibrated probability",
        "overlap_seconds": end_l - start_l,
        "crop_if_audio_and_video_share_time_zero": {
            "left_start_seconds": start_l,
            "right_start_seconds": start_l + offset,
            "duration_seconds": end_l - start_l,
        },
        "limits": "One constant offset only; does not correct clock drift or audio/video PTS offsets",
    }


def plot_alignment(left: np.ndarray, right: np.ndarray, result: dict, destination: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    env_l, env_r = envelope(left), envelope(right)
    fig, axes = plt.subplots(3, 1, figsize=(10, 8))
    time_l = np.arange(len(env_l)) / ENVELOPE_RATE
    time_r = np.arange(len(env_r)) / ENVELOPE_RATE
    norm_l = env_l / max(env_l.max(), 1e-12)
    norm_r = env_r / max(env_r.max(), 1e-12)
    axes[0].plot(time_l, norm_l, label="Left")
    axes[0].plot(time_r, norm_r, alpha=0.7, label="Right")
    axes[0].set(xlabel="Each recording's local time (s)", ylabel="Envelope", title="Before alignment")
    axes[0].legend()
    axes[1].plot(time_l, norm_l, label="Left")
    axes[1].plot(time_r - result["offset_seconds"], norm_r, alpha=0.7, label="Right on left timeline")
    axes[1].set(xlabel="Left recording time (s)", ylabel="Envelope", title=f'After alignment: t_right = t_left + {result["offset_seconds"]:+.6f} s')
    axes[1].legend()
    offsets, corr, overlap = normalized_correlation(env_l, env_r)
    width = max(3.0, abs(result["offset_seconds"]) + 0.5)
    use = (np.abs(offsets) <= width) & np.isfinite(corr) & (overlap >= 2.0)
    axes[2].plot(offsets[use], corr[use], label="Overlap-normalized correlation")
    axes[2].axvline(result["offset_seconds"], color="tab:red", linestyle="--", label="Accepted peak")
    axes[2].set(xlabel="Candidate offset: right time minus left time (s)", ylabel="Correlation", title="One strong match; competing peaks are checked")
    axes[2].legend()
    fig.tight_layout()
    fig.savefig(destination, dpi=150)
    plt.close(fig)


def _synthetic_audio(rate: int, start: float, duration: float, gain: float, seed: int) -> np.ndarray:
    """Sample the same artificial acoustic world on different local clocks."""
    t = start + np.arange(round(rate * duration)) / rate
    rng = np.random.default_rng(20261110)
    centers = rng.uniform(1.0, 18.0, 28)
    widths = rng.uniform(0.04, 0.17, len(centers))
    heights = rng.uniform(0.2, 0.9, len(centers))
    amp = 0.015 + sum(h * np.exp(-0.5 * ((t - c) / w)**2) for c, w, h in zip(centers, widths, heights))
    carrier = 0.6 * np.sin(2 * np.pi * 431 * t) + 0.25 * np.sin(2 * np.pi * 947 * t)
    return (gain * amp * carrier + np.random.default_rng(seed).normal(0, 0.003, len(t))).astype(np.float32)


def self_test(plot: Path | None = None) -> dict:
    checks = []
    with tempfile.TemporaryDirectory(prefix="specialist-audio-test-") as tmp:
        for name, rate_l, rate_r, start_l, start_r in [
            ("negative_offset_unequal_rates", 12_000, 22_050, 0.0, 0.613),
            ("positive_offset_gain_and_noise", 16_000, 16_000, 0.827, 0.0),
        ]:
            pl, pr = Path(tmp) / "left.wav", Path(tmp) / "right.wav"
            samples_l = _synthetic_audio(rate_l, start_l, 19.0, 0.65, 11)
            samples_r = _synthetic_audio(rate_r, start_r, 19.0, 0.3, 17)
            if name.startswith("positive"):
                samples_l = (np.clip(samples_l, -1, 1) * 32767).astype(np.int16)
                samples_r = (np.clip(samples_r, -1, 1) * 32767).astype(np.int16)
            wavfile.write(pl, rate_l, samples_l)
            wavfile.write(pr, rate_r, samples_r)
            decoded_l, decoded_r = read_wav(pl), read_wav(pr)
            result = estimate_offset(decoded_l, decoded_r, max_offset=3)
            if plot and name.startswith("positive"):
                plot_alignment(decoded_l, decoded_r, result, plot)
            expected = start_l - start_r
            assert abs(result["offset_seconds"] - expected) < 0.003, (name, expected, result)
            crop = result["crop_if_audio_and_video_share_time_zero"]
            assert abs(start_l + crop["left_start_seconds"] - start_r - crop["right_start_seconds"]) < 0.003
            checks.append({"test": name, "expected_offset_seconds": expected, "estimated_offset_seconds": result["offset_seconds"], "passed": True})
        silent = Path(tmp) / "silent.wav"
        wavfile.write(silent, AUDIO_RATE, np.zeros(AUDIO_RATE * 3, dtype=np.int16))
        try:
            read_wav(silent)
        except AlignmentError:
            checks.append({"test": "silence_rejected", "passed": True})
        else:
            raise AssertionError("Silent audio was accepted")
        t = np.arange(AUDIO_RATE * 12) / AUDIO_RATE
        periodic = lambda times: (0.4 + 0.3 * np.cos(2 * np.pi * 2 * times)) * np.sin(2 * np.pi * 431 * times)
        try:
            estimate_offset(periodic(t), periodic(t + 0.37), max_offset=3)
        except AlignmentError as e:
            assert "Ambiguous" in str(e), str(e)
            checks.append({"test": "periodic_audio_rejected", "passed": True})
        else:
            raise AssertionError("Periodic ambiguous audio was accepted")
    return {"status": "passed", "tests": checks, "note": "Synthetic tests verify implementation/sign handling; they do not validate real-camera synchronization accuracy"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("left", nargs="?", type=Path)
    parser.add_argument("right", nargs="?", type=Path)
    parser.add_argument("--max-offset", type=float, default=30.0)
    parser.add_argument("--min-overlap", type=float, default=2.0)
    parser.add_argument("--min-correlation", type=float, default=0.5)
    parser.add_argument("--min-peak-ratio", type=float, default=1.3)
    parser.add_argument("--plot", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        if args.self_test:
            result = self_test(args.plot)
        else:
            if args.left is None or args.right is None:
                parser.error("Supply left.wav and right.wav, or --self-test")
            left, right = read_wav(args.left), read_wav(args.right)
            result = estimate_offset(left, right, max_offset=args.max_offset, min_overlap=args.min_overlap, min_correlation=args.min_correlation, min_peak_ratio=args.min_peak_ratio)
            if args.plot:
                plot_alignment(left, right, result, args.plot)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (AlignmentError, OSError, ValueError) as error:
        print(json.dumps({"status": "rejected", "reason": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
