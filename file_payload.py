from __future__ import annotations

import base64
import json
import re
from pathlib import Path


FRAME_PREFIX = "SONICFILE:"


def make_file_payload(path: str | Path) -> str:
    source = Path(path)
    data = source.read_bytes()
    payload = {
        "name": source.name,
        "size": len(data),
        "data": base64.b64encode(data).decode("ascii"),
    }
    return FRAME_PREFIX + json.dumps(payload, separators=(",", ":"))


def save_file_payload(message: str, output_dir: str | Path = "received") -> Path | None:
    if not message.startswith(FRAME_PREFIX):
        return None

    payload = json.loads(message[len(FRAME_PREFIX) :])
    raw_name = str(payload["name"])
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name).strip("._") or "received.bin"
    data = base64.b64decode(payload["data"])

    expected_size = int(payload["size"])
    if len(data) != expected_size:
        raise ValueError(f"Decoded size mismatch: expected {expected_size}, got {len(data)}")

    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    destination = out_dir / safe_name
    destination.write_bytes(data)
    return destination
