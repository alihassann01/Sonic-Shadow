from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class SonicConfig:
    sample_rate: int = 44_100
    bit_duration: float = 0.1
    freq_zero: float = 18_000.0
    freq_one: float = 19_000.0
    sync_freq: float = 17_500.0
    tolerance: float = 250.0
    amplitude: float = 0.35
    repeat_bits: int = 1

    @property
    def samples_per_symbol(self) -> int:
        return int(self.sample_rate * self.bit_duration)


DEFAULT_CONFIG = SonicConfig()
SYNC_SYMBOLS = 8


def text_to_bits(text: str) -> str:
    data = text.encode("utf-8")
    return "".join(f"{byte:08b}" for byte in data)


def bits_to_text(bits: str) -> str:
    usable_length = len(bits) - (len(bits) % 8)
    data = bytearray()
    for index in range(0, usable_length, 8):
        data.append(int(bits[index : index + 8], 2))
    return data.decode("utf-8", errors="replace")


def majority_vote(bits: Iterable[str], group_size: int) -> str:
    if group_size <= 1:
        return "".join(bits)

    bit_list = list(bits)
    decoded: list[str] = []
    for index in range(0, len(bit_list), group_size):
        group = bit_list[index : index + group_size]
        if len(group) < group_size:
            break
        decoded.append("1" if group.count("1") > group.count("0") else "0")
    return "".join(decoded)


def generate_tone(freq: float, config: SonicConfig = DEFAULT_CONFIG) -> np.ndarray:
    samples = config.samples_per_symbol
    t = np.arange(samples, dtype=np.float32) / config.sample_rate
    wave = np.sin(2 * np.pi * freq * t)

    fade_samples = min(int(config.sample_rate * 0.005), samples // 2)
    if fade_samples > 0:
        fade = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
        wave[:fade_samples] *= fade
        wave[-fade_samples:] *= fade[::-1]

    return (config.amplitude * wave).astype(np.float32)


def encode_message(text: str, config: SonicConfig = DEFAULT_CONFIG) -> np.ndarray:
    bits = text_to_bits(text)
    repeated_bits = "".join(bit * config.repeat_bits for bit in bits)
    freqs = [config.sync_freq] * SYNC_SYMBOLS
    freqs.extend(config.freq_one if bit == "1" else config.freq_zero for bit in repeated_bits)
    freqs.extend([config.sync_freq] * SYNC_SYMBOLS)
    return np.concatenate([generate_tone(freq, config) for freq in freqs])


def dominant_frequency(chunk: np.ndarray, sample_rate: int, min_frequency: float = 15_000.0) -> tuple[float, float]:
    if chunk.size == 0:
        return 0.0, 0.0

    mono = np.asarray(chunk, dtype=np.float32).reshape(-1)
    windowed = mono * np.hanning(mono.size)
    spectrum = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(mono.size, 1 / sample_rate)

    target_band = freqs >= min_frequency
    if not np.any(target_band):
        return 0.0, 0.0

    local_index = int(np.argmax(spectrum[target_band]))
    candidate_freqs = freqs[target_band]
    candidate_power = spectrum[target_band]
    return float(candidate_freqs[local_index]), float(candidate_power[local_index])


def tone_powers(chunk: np.ndarray, config: SonicConfig = DEFAULT_CONFIG) -> dict[str, tuple[float, float]]:
    if chunk.size == 0:
        return {"S": (config.sync_freq, 0.0), "0": (config.freq_zero, 0.0), "1": (config.freq_one, 0.0)}

    mono = np.asarray(chunk, dtype=np.float32).reshape(-1)
    windowed = mono * np.hanning(mono.size)
    spectrum = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(mono.size, 1 / config.sample_rate)

    candidates = {
        "S": config.sync_freq,
        "0": config.freq_zero,
        "1": config.freq_one,
    }
    powers: dict[str, tuple[float, float]] = {}
    for symbol, target in candidates.items():
        band = np.abs(freqs - target) <= config.tolerance
        powers[symbol] = (target, float(np.max(spectrum[band])) if np.any(band) else 0.0)

    return powers


def detect_symbol(chunk: np.ndarray, config: SonicConfig = DEFAULT_CONFIG) -> tuple[str | None, float, float]:
    powers_with_freqs = tone_powers(chunk, config)
    powers = {symbol: value[1] for symbol, value in powers_with_freqs.items()}
    candidates = {symbol: value[0] for symbol, value in powers_with_freqs.items()}

    mono = np.asarray(chunk, dtype=np.float32).reshape(-1)
    if mono.size == 0:
        return None, 0.0, 0.0

    windowed = mono * np.hanning(mono.size)
    spectrum = np.abs(np.fft.rfft(windowed))

    ordered = sorted(powers.items(), key=lambda item: item[1], reverse=True)
    best_symbol, best_power = ordered[0]
    second_power = ordered[1][1]
    noise_floor = float(np.median(spectrum) + 1e-9)

    if best_power < noise_floor * 3:
        return None, candidates[best_symbol], best_power
    if second_power > 0 and best_power < second_power * 1.03:
        return None, candidates[best_symbol], best_power

    return best_symbol, candidates[best_symbol], best_power


def classify_frequency(freq: float, config: SonicConfig = DEFAULT_CONFIG) -> str | None:
    if abs(freq - config.sync_freq) <= config.tolerance:
        return "S"
    if abs(freq - config.freq_zero) <= config.tolerance:
        return "0"
    if abs(freq - config.freq_one) <= config.tolerance:
        return "1"
    return None


def demo_config(audible: bool = False, repeat_bits: int = 1) -> SonicConfig:
    if not audible:
        return SonicConfig(repeat_bits=repeat_bits)
    return SonicConfig(
        freq_zero=1_000.0,
        freq_one=2_000.0,
        sync_freq=1_500.0,
        tolerance=180.0,
        repeat_bits=repeat_bits,
    )


def make_config(
    *,
    audible: bool = False,
    repeat_bits: int = 1,
    bit_duration: float | None = None,
    freq_zero: float | None = None,
    freq_one: float | None = None,
    sync_freq: float | None = None,
    tolerance: float | None = None,
) -> SonicConfig:
    base = demo_config(audible=audible, repeat_bits=repeat_bits)
    return SonicConfig(
        sample_rate=base.sample_rate,
        bit_duration=bit_duration if bit_duration is not None else base.bit_duration,
        freq_zero=freq_zero if freq_zero is not None else base.freq_zero,
        freq_one=freq_one if freq_one is not None else base.freq_one,
        sync_freq=sync_freq if sync_freq is not None else base.sync_freq,
        tolerance=tolerance if tolerance is not None else base.tolerance,
        amplitude=base.amplitude,
        repeat_bits=repeat_bits,
    )
