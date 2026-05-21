from __future__ import annotations

import argparse
import sys
from pathlib import Path

import sounddevice as sd
from rich.console import Console
from rich.panel import Panel

from file_payload import make_file_payload
from profiles import add_profile_argument, apply_profile
from protocol import encode_message, generate_tone, make_config, text_to_bits


console = Console()


def read_message(args: argparse.Namespace) -> str:
    if args.message is not None:
        return args.message
    if args.binary_file is not None:
        return make_file_payload(args.binary_file)
    if args.file is not None:
        return Path(args.file).read_text(encoding="utf-8")
    return sys.stdin.read() if not sys.stdin.isatty() else input("Message to transmit: ")


def transmit(
    message: str,
    *,
    audible: bool = False,
    repeat_bits: int = 1,
    device: int | None = None,
    freq_zero: float | None = None,
    freq_one: float | None = None,
    sync_freq: float | None = None,
    tolerance: float | None = None,
    bit_duration: float | None = None,
) -> None:
    config = make_config(
        audible=audible,
        repeat_bits=repeat_bits,
        bit_duration=bit_duration,
        freq_zero=freq_zero,
        freq_one=freq_one,
        sync_freq=sync_freq,
        tolerance=tolerance,
    )
    waveform = encode_message(message, config)
    seconds = waveform.size / config.sample_rate
    bits = len(text_to_bits(message))

    console.print(
        Panel.fit(
            f"Mode: {'audible test' if audible else 'ultrasonic lab demo'}\n"
            f"Payload: {len(message)} chars / {bits} bits\n"
            f"Duration: {seconds:.2f}s\n"
            f"Frequencies: 0={config.freq_zero:.0f} Hz, 1={config.freq_one:.0f} Hz, sync={config.sync_freq:.0f} Hz",
            title="SonicShadow Transmitter",
        )
    )

    sd.play(waveform, samplerate=config.sample_rate, device=device, blocking=True)
    console.print("[green]Transmission complete.[/green]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Controlled SonicShadow lab transmitter. Sends an explicit message as BFSK audio."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("-m", "--message", help="Message to transmit.")
    source.add_argument("-f", "--file", help="Text file to transmit. Use demo.txt for the lab demo.")
    source.add_argument("--binary-file", help="Explicitly selected file to package and transmit as Base64.")
    source.add_argument("--tone", type=float, help="Play one continuous calibration tone instead of a message.")
    parser.add_argument("--tone-seconds", type=float, default=5.0, help="Length of --tone playback.")
    parser.add_argument("--audible", action="store_true", help="Use 1-2 kHz tones for debugging.")
    parser.add_argument("--repeat-bits", type=int, default=1, choices=(1, 3, 5), help="Repeat bits for reliability.")
    parser.add_argument("--freq-zero", type=float, help="Override bit-0 frequency.")
    parser.add_argument("--freq-one", type=float, help="Override bit-1 frequency.")
    parser.add_argument("--sync-freq", type=float, help="Override sync frequency.")
    parser.add_argument("--tolerance", type=float, help="Override decoder tolerance note shown in protocol.")
    parser.add_argument("--bit-duration", type=float, help="Seconds per BFSK tone. Default is 0.1.")
    add_profile_argument(parser)
    parser.add_argument("--device", type=int, help="Optional sounddevice output device id.")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices and exit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    apply_profile(args)
    if args.list_devices:
        console.print(sd.query_devices())
        return

    if args.tone is not None:
        config = make_config(
            audible=args.audible,
            repeat_bits=args.repeat_bits,
            bit_duration=args.tone_seconds,
            freq_zero=args.freq_zero,
            freq_one=args.freq_one,
            sync_freq=args.sync_freq,
            tolerance=args.tolerance,
        )
        console.print(f"[cyan]Playing calibration tone:[/cyan] {args.tone:.0f} Hz for {args.tone_seconds:.1f}s")
        sd.play(generate_tone(args.tone, config), samplerate=config.sample_rate, device=args.device, blocking=True)
        console.print("[green]Tone complete.[/green]")
        return

    message = read_message(args).strip()
    if not message:
        console.print("[red]Nothing to transmit.[/red]")
        raise SystemExit(1)

    if not args.audible:
        console.print(
            "[yellow]Lab safety:[/yellow] run this only with your own demo text and nearby consenting receiver."
        )

    transmit(
        message,
        audible=args.audible,
        repeat_bits=args.repeat_bits,
        device=args.device,
        freq_zero=args.freq_zero,
        freq_one=args.freq_one,
        sync_freq=args.sync_freq,
        tolerance=args.tolerance,
        bit_duration=args.bit_duration,
    )


if __name__ == "__main__":
    main()
