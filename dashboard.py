from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from file_payload import make_file_payload
from profiles import PROFILES, estimate_seconds
from receiver import receive
from transmitter import transmit


console = Console()


def profile_table() -> Table:
    table = Table(title="SonicShadow Demo Profiles")
    table.add_column("Key")
    table.add_column("0 Hz", justify="right")
    table.add_column("1 Hz", justify="right")
    table.add_column("Sync", justify="right")
    table.add_column("Bit")
    table.add_column("Repeat")
    table.add_column("Notes")

    for key, profile in PROFILES.items():
        table.add_row(
            key,
            f"{profile.freq_zero:.0f}",
            f"{profile.freq_one:.0f}",
            f"{profile.sync_freq:.0f}",
            f"{profile.bit_duration:.2f}s",
            str(profile.repeat_bits),
            profile.description,
        )
    return table


def choose_profile(default: str) -> str:
    console.print(profile_table())
    choice = console.input(f"\nProfile [{default}]: ").strip() or default
    while choice not in PROFILES:
        console.print("[red]Unknown profile.[/red]")
        choice = console.input(f"Profile [{default}]: ").strip() or default
    return choice


def make_receiver_args(profile_key: str, device: int | None, save_files: bool) -> SimpleNamespace:
    profile = PROFILES[profile_key]
    return SimpleNamespace(
        audible=False,
        repeat_bits=profile.repeat_bits,
        freq_zero=profile.freq_zero,
        freq_one=profile.freq_one,
        sync_freq=profile.sync_freq,
        tolerance=profile.tolerance,
        bit_duration=profile.bit_duration,
        save_files=save_files,
        monitor=False,
        device=device,
        list_devices=False,
        max_symbols=4096,
        idle_timeout=2.0,
        self_test=None,
    )


def run_transmit(profile_key: str, device: int | None, message: str) -> None:
    profile = PROFILES[profile_key]
    seconds = estimate_seconds(len(message), profile.bit_duration, profile.repeat_bits)
    console.print(f"[cyan]Estimated time:[/cyan] {seconds:.1f}s")
    transmit(
        message,
        repeat_bits=profile.repeat_bits,
        device=device,
        freq_zero=profile.freq_zero,
        freq_one=profile.freq_one,
        sync_freq=profile.sync_freq,
        tolerance=profile.tolerance,
        bit_duration=profile.bit_duration,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rich terminal dashboard for SonicShadow lab demos.")
    parser.add_argument("--input-device", type=int, default=1)
    parser.add_argument("--output-device", type=int, default=3)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="reliable_slow")
    args = parser.parse_args()

    profile_key = choose_profile(args.profile)
    console.print(
        Panel.fit(
            "1. Receive message\n"
            "2. Transmit typed message\n"
            "3. Transmit demo.txt\n"
            "4. Transmit selected file payload\n"
            "5. Show spectrogram command\n"
            "6. Exit",
            title="SonicShadow Dashboard",
        )
    )

    choice = console.input("Action: ").strip()
    if choice == "1":
        receive(make_receiver_args(profile_key, args.input_device, save_files=True))
    elif choice == "2":
        message = console.input("Message: ")
        run_transmit(profile_key, args.output_device, message)
    elif choice == "3":
        message = Path("demo.txt").read_text(encoding="utf-8").strip()
        run_transmit(profile_key, args.output_device, message)
    elif choice == "4":
        path = console.input("File path inside your lab/project folder: ").strip().strip('"')
        run_transmit(profile_key, args.output_device, make_file_payload(path))
    elif choice == "5":
        profile = PROFILES[profile_key]
        console.print(
            Panel(
                "Run this in another terminal:\n\n"
                f"python spectrogram.py --device {args.input_device} "
                f"--freq-zero {profile.freq_zero:.0f} --freq-one {profile.freq_one:.0f} "
                f"--sync-freq {profile.sync_freq:.0f} --tolerance {profile.tolerance:.0f} "
                f"--bit-duration {profile.bit_duration}",
                title="Spectrogram",
            )
        )
    else:
        console.print("Done.")


if __name__ == "__main__":
    main()
