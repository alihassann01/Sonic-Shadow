from __future__ import annotations

import argparse
from collections import deque

import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd
from scipy.signal import spectrogram

from profiles import add_profile_argument, apply_profile
from protocol import make_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live spectrogram for the SonicShadow lab demo.")
    parser.add_argument("--audible", action="store_true", help="Show 0-4 kHz range for audible testing.")
    parser.add_argument("--freq-zero", type=float, help="Override bit-0 frequency.")
    parser.add_argument("--freq-one", type=float, help="Override bit-1 frequency.")
    parser.add_argument("--sync-freq", type=float, help="Override sync frequency.")
    parser.add_argument("--tolerance", type=float, help="Override frequency tolerance.")
    add_profile_argument(parser)
    parser.add_argument("--device", type=int, help="Optional sounddevice input device id.")
    parser.add_argument("--seconds", type=float, default=4.0, help="Rolling display window.")
    parser.add_argument("--bit-duration", type=float, help="Seconds per BFSK tone. Default is 0.1.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    apply_profile(args)
    config = make_config(
        audible=args.audible,
        bit_duration=args.bit_duration,
        freq_zero=args.freq_zero,
        freq_one=args.freq_one,
        sync_freq=args.sync_freq,
        tolerance=args.tolerance,
    )
    chunk_size = config.samples_per_symbol
    max_chunks = max(1, int(args.seconds / config.bit_duration))
    chunks: deque[np.ndarray] = deque(maxlen=max_chunks)

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.canvas.manager.set_window_title("SonicShadow Spectrogram")

    with sd.InputStream(
        samplerate=config.sample_rate,
        blocksize=chunk_size,
        channels=1,
        dtype="float32",
        device=args.device,
    ) as stream:
        while plt.fignum_exists(fig.number):
            chunk, _ = stream.read(chunk_size)
            chunks.append(np.asarray(chunk).reshape(-1))
            audio = np.concatenate(list(chunks))

            freqs, times, power = spectrogram(audio, fs=config.sample_rate, nperseg=1024, noverlap=768)
            if args.audible:
                lower, upper = 0, 4_000
            else:
                profile_min = min(config.freq_zero, config.freq_one, config.sync_freq)
                profile_max = max(config.freq_zero, config.freq_one, config.sync_freq)
                lower = max(0, profile_min - 1_500)
                upper = min(config.sample_rate / 2, profile_max + 1_500)
            band = (freqs >= lower) & (freqs <= upper)

            ax.clear()
            ax.pcolormesh(times, freqs[band], 10 * np.log10(power[band] + 1e-12), shading="auto", cmap="magma")
            ax.set_title("Live BFSK Frequency Bands")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Frequency (Hz)")
            ax.set_ylim(lower, upper)
            ax.axhline(config.freq_zero, color="#3ddc97", linewidth=1)
            ax.axhline(config.freq_one, color="#39a0ff", linewidth=1)
            ax.axhline(config.sync_freq, color="#ffcc00", linewidth=1)
            plt.pause(0.001)


if __name__ == "__main__":
    main()
