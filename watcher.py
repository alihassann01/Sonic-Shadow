from __future__ import annotations

import argparse
import time
from pathlib import Path

from rich.console import Console
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from transmitter import transmit


console = Console()


class DemoFileHandler(FileSystemEventHandler):
    def __init__(self, target: Path, audible: bool, repeat_bits: int) -> None:
        self.target = target.resolve()
        self.audible = audible
        self.repeat_bits = repeat_bits
        self.last_sent = 0.0

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        changed = Path(event.src_path).resolve()
        if changed != self.target:
            return

        now = time.monotonic()
        if now - self.last_sent < 0.8:
            return
        self.last_sent = now

        message = self.target.read_text(encoding="utf-8").strip()
        if not message:
            console.print("[yellow]demo.txt is empty; skipping transmission.[/yellow]")
            return

        console.print(f"[cyan]Detected change in {self.target.name}; transmitting demo payload.[/cyan]")
        transmit(message, audible=self.audible, repeat_bits=self.repeat_bits)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Controlled file watcher for the SonicShadow lab demo. Watches demo.txt by default."
    )
    parser.add_argument("--file", default="demo.txt", help="Demo text file to watch.")
    parser.add_argument("--audible", action="store_true", help="Use 1-2 kHz tones for debugging.")
    parser.add_argument("--repeat-bits", type=int, default=1, choices=(1, 3, 5), help="Repeat bits for reliability.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target = Path(args.file).resolve()
    if target.name.lower() != "demo.txt":
        console.print("[red]Safety guard: watcher.py only watches a lab file named demo.txt.[/red]")
        raise SystemExit(1)

    target.touch(exist_ok=True)
    observer = Observer()
    observer.schedule(DemoFileHandler(target, args.audible, args.repeat_bits), str(target.parent), recursive=False)
    observer.start()

    console.print(f"[green]Watching {target}[/green]")
    console.print("Edit demo.txt to trigger a controlled transmission. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
