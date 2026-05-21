from __future__ import annotations

import argparse
from collections import deque

import numpy as np
import sounddevice as sd
from rich.console import Console
from rich.live import Live
from rich.panel import Panel

from file_payload import save_file_payload
from profiles import add_profile_argument, apply_profile
from protocol import (
    SYNC_SYMBOLS,
    bits_to_text,
    classify_frequency,
    dominant_frequency,
    detect_symbol,
    encode_message,
    make_config,
    majority_vote,
    tone_powers,
)


console = Console()


def visible_text(text: str) -> str:
    if not text:
        return ""
    return text.encode("unicode_escape").decode("ascii")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Controlled SonicShadow lab receiver. Decodes BFSK audio from microphone input."
    )
    parser.add_argument("--audible", action="store_true", help="Use 1-2 kHz tones for debugging.")
    parser.add_argument("--repeat-bits", type=int, default=1, choices=(1, 3, 5), help="Bit repetition used by transmitter.")
    parser.add_argument("--freq-zero", type=float, help="Override bit-0 frequency.")
    parser.add_argument("--freq-one", type=float, help="Override bit-1 frequency.")
    parser.add_argument("--sync-freq", type=float, help="Override sync frequency.")
    parser.add_argument("--tolerance", type=float, help="Override frequency tolerance.")
    parser.add_argument("--bit-duration", type=float, help="Seconds per BFSK tone. Must match transmitter.")
    add_profile_argument(parser)
    parser.add_argument("--save-files", action="store_true", help="Save explicit SONICFILE payloads into received/.")
    parser.add_argument("--monitor", action="store_true", help="Only show tone powers; do not decode.")
    parser.add_argument("--device", type=int, help="Optional sounddevice input device id.")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices and exit.")
    parser.add_argument("--max-symbols", type=int, default=4096, help="Stop after this many symbols.")
    parser.add_argument("--idle-timeout", type=float, default=2.0, help="Stop this many seconds after valid symbols end.")
    parser.add_argument("--self-test", help="Decode this message from generated audio without using the microphone.")
    return parser.parse_args()


def monitor(args: argparse.Namespace) -> None:
    config = make_config(
        audible=args.audible,
        repeat_bits=args.repeat_bits,
        bit_duration=args.bit_duration,
        freq_zero=args.freq_zero,
        freq_one=args.freq_one,
        sync_freq=args.sync_freq,
        tolerance=args.tolerance,
    )
    chunk_size = config.samples_per_symbol
    try:
        with sd.InputStream(
            samplerate=config.sample_rate,
            blocksize=chunk_size,
            channels=1,
            dtype="float32",
            device=args.device,
        ) as stream, Live(render_status(0.0, 0.0, None, "", False), refresh_per_second=8) as live:
            while True:
                chunk, _ = stream.read(chunk_size)
                chunk_array = np.asarray(chunk).reshape(-1)
                powers = tone_powers(chunk_array, config)
                symbol, freq, power = detect_symbol(chunk_array, config)
                live.update(render_status(freq, power, symbol, "", False, 0, powers))
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped by user.[/yellow]")


def render_status(
    freq: float,
    power: float,
    symbol: str | None,
    decoded: str,
    listening: bool,
    bit_count: int = 0,
    powers: dict[str, tuple[float, float]] | None = None,
) -> Panel:
    state = "receiving" if listening else "waiting for sync"
    power_line = ""
    if powers:
        power_line = (
            f"\nSync power: {powers['S'][1]:10.2f}"
            f" | 0 power: {powers['0'][1]:10.2f}"
            f" | 1 power: {powers['1'][1]:10.2f}"
        )
    return Panel(
        f"State: {state}\n"
        f"Dominant frequency: {freq:8.1f} Hz\n"
        f"Tone power: {power:12.2f}\n"
        f"Last symbol: {symbol or '-'}\n"
        f"Bits captured: {bit_count}{power_line}\n\n"
        f"Decoded text:\n{visible_text(decoded)}",
        title="SonicShadow Receiver",
    )


def receive(args: argparse.Namespace) -> None:
    config = make_config(
        audible=args.audible,
        repeat_bits=args.repeat_bits,
        bit_duration=args.bit_duration,
        freq_zero=args.freq_zero,
        freq_one=args.freq_one,
        sync_freq=args.sync_freq,
        tolerance=args.tolerance,
    )
    chunk_size = config.samples_per_symbol
    sync_window: deque[str] = deque(maxlen=SYNC_SYMBOLS)
    bits: list[str] = []
    receiving = False
    decoded = ""
    idle_symbols = 0
    max_idle_symbols = max(1, int(args.idle_timeout / config.bit_duration))

    console.print(
        "[yellow]Lab receiver:[/yellow] start this before running transmitter.py. "
        "Use --audible first while testing."
    )

    try:
        with sd.InputStream(
            samplerate=config.sample_rate,
            blocksize=chunk_size,
            channels=1,
            dtype="float32",
            device=args.device,
        ) as stream, Live(render_status(0.0, 0.0, None, decoded, receiving), refresh_per_second=8) as live:
            for _ in range(args.max_symbols):
                chunk, overflowed = stream.read(chunk_size)
                if overflowed:
                    console.print("[yellow]Input overflow detected; consider closing other audio apps.[/yellow]")

                chunk_array = np.asarray(chunk).reshape(-1)
                powers = tone_powers(chunk_array, config)
                symbol, freq, power = detect_symbol(chunk_array, config)

                if symbol == "S":
                    idle_symbols = 0
                    sync_window.append("S")
                    if receiving and len(sync_window) == SYNC_SYMBOLS:
                        break
                    if not receiving and len(sync_window) == SYNC_SYMBOLS:
                        receiving = True
                        bits.clear()
                        sync_window.clear()
                elif receiving and symbol in {"0", "1"}:
                    idle_symbols = 0
                    sync_window.clear()
                    bits.append(symbol)
                    voted = majority_vote(bits, config.repeat_bits)
                    decoded = bits_to_text(voted)
                elif receiving:
                    idle_symbols += 1
                    sync_window.clear()
                    if bits and idle_symbols >= max_idle_symbols:
                        console.print("\n[yellow]No valid symbols detected; stopping receiver.[/yellow]")
                        break

                live.update(render_status(freq, power, symbol, decoded, receiving, len(bits), powers))
    except KeyboardInterrupt:
        console.print("\n[yellow]Receiver stopped by user.[/yellow]")

    console.print(Panel(visible_text(decoded) or "No message decoded.", title="Final Decoded Message"))
    if decoded and args.save_files:
        try:
            destination = save_file_payload(decoded)
        except Exception as error:
            console.print(f"[red]Could not save file payload:[/red] {error}")
        else:
            if destination:
                console.print(f"[green]Saved received file:[/green] {destination}")


def self_test(args: argparse.Namespace) -> None:
    config = make_config(
        audible=args.audible,
        repeat_bits=args.repeat_bits,
        bit_duration=args.bit_duration,
        freq_zero=args.freq_zero,
        freq_one=args.freq_one,
        sync_freq=args.sync_freq,
        tolerance=args.tolerance,
    )
    wave = encode_message(args.self_test, config)
    chunk_size = config.samples_per_symbol
    min_frequency = 500.0 if args.audible else 15_000.0
    receiving = False
    sync_count = 0
    end_sync_count = 0
    bits: list[str] = []

    for index in range(0, wave.size, chunk_size):
        chunk = wave[index : index + chunk_size]
        symbol, freq, _ = detect_symbol(chunk, config)

        if symbol == "S":
            if receiving:
                end_sync_count += 1
                if end_sync_count >= SYNC_SYMBOLS:
                    break
            else:
                sync_count += 1
                if sync_count >= SYNC_SYMBOLS:
                    receiving = True
            continue

        if not receiving:
            sync_count = 0
            continue

        end_sync_count = 0
        if symbol in {"0", "1"}:
            bits.append(symbol)

    decoded = bits_to_text(majority_vote(bits, config.repeat_bits))
    console.print(Panel(decoded, title="Receiver Self-Test Decoded Message"))


def main() -> None:
    args = parse_args()
    apply_profile(args)
    if args.list_devices:
        console.print(sd.query_devices())
        return
    if args.self_test is not None:
        self_test(args)
        return
    if args.monitor:
        monitor(args)
        return
    receive(args)


if __name__ == "__main__":
    main()
