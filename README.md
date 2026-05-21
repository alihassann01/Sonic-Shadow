# SonicShadow

SonicShadow is a controlled Operating Systems lab demo that sends an explicit text message over audio using Binary Frequency Shift Keying (BFSK). It is designed to demonstrate OS audio APIs, buffering, FFT-based signal analysis, file-system events, and live spectrogram visualization.

Use this only with your own demo text and a consenting receiver in a lab setting. The watcher is intentionally limited to a file named `demo.txt`.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If audio input/output devices are confusing, list them:

```bash
python transmitter.py --list-devices
python receiver.py --list-devices
```

## Recommended Test Flow

The validated profile on this laptop is available as a shortcut:

```bash
python receiver.py --device 1 --profile reliable_slow
python transmitter.py --device 3 --profile reliable_slow --file demo.txt
```

Start with audible tones first:

```bash
python receiver.py --audible
```

In another terminal:

```bash
python transmitter.py --audible --message "HELLO OS LAB"
```

Once that works, try the ultrasonic lab mode:

```bash
python receiver.py
python transmitter.py --message "HELLO OS LAB"
```

If 18-19 kHz is unstable on your laptop, use a lower near-ultrasonic profile. This is more likely to survive laptop speakers and microphones, but it may be faintly audible to some people:

```bash
python receiver.py --freq-zero 17000 --freq-one 18000 --sync-freq 16500 --repeat-bits 3
python transmitter.py --freq-zero 17000 --freq-one 18000 --sync-freq 16500 --repeat-bits 3 --message "HELLO OS LAB"
```

If decoding is unstable, repeat each bit three times on both sides:

```bash
python receiver.py --repeat-bits 3
python transmitter.py --repeat-bits 3 --message "HELLO OS LAB"
```

Use shorter bit durations for faster demos. The same value must be used on both sides:

```bash
python receiver.py --bit-duration 0.05
python transmitter.py --bit-duration 0.05 --message "HELLO OS LAB"
```

## Explicit File Transfer Demo

For a stronger demo, transmit a selected file as a Base64 payload and let the receiver save it into `received/`. Keep files small because audio transfer is slow.

```bash
python receiver.py --save-files --repeat-bits 3
python transmitter.py --binary-file demo.txt --repeat-bits 3
```

That reliable mode is slow because Base64 adds overhead and `--repeat-bits 3` triples the data. For a faster small-file demo:

```bash
python receiver.py --save-files --bit-duration 0.05
python transmitter.py --binary-file demo.txt --bit-duration 0.05
```

With the lower near-ultrasonic profile:

```bash
python receiver.py --save-files --freq-zero 17000 --freq-one 18000 --sync-freq 16500 --repeat-bits 3
python transmitter.py --binary-file demo.txt --freq-zero 17000 --freq-one 18000 --sync-freq 16500 --repeat-bits 3
```

This is intentionally explicit and consent-based: you choose the file, the transmitter announces what it is doing, and the receiver only saves a framed payload when `--save-files` is used.

## File Watcher Demo

The watcher demonstrates OS file-system monitoring with `watchdog`.

```bash
python receiver.py --audible
python watcher.py --audible
```

Then edit `demo.txt`. Every save triggers a controlled transmission of that file.

## Spectrogram

Run this in a separate terminal to show the live frequency bands:

```bash
python spectrogram.py --device 1 --profile reliable_slow
```

For ultrasonic mode:

```bash
python spectrogram.py
```

## Dashboard

For a cleaner viva/demo flow:

```bash
python dashboard.py
```

The dashboard lets you choose the validated profile, receive, transmit a typed message, transmit `demo.txt`, or print the matching spectrogram command.

## Browser Frontend

The `frontend/` folder contains a browser UI that can transmit tones, receive through the microphone, and draw a live spectrogram. Start a local static server from the project root:

```bash
python -m http.server 8000 --directory frontend
```

Then open:

```text
http://localhost:8000
```

Use the `Reliable slow` profile first. Click `Start Listening` in one browser window, then use `Play Transmission` in another window or another device. The browser will ask for microphone permission.

## Files

- `protocol.py` contains the BFSK protocol, tone generation, FFT frequency detection, and bit/text conversion.
- `transmitter.py` converts text to tones and plays them through the OS audio stack.
- `receiver.py` records microphone chunks, applies FFT, classifies tones, and reconstructs text.
- `spectrogram.py` shows a live waterfall-style frequency visualization.
- `watcher.py` watches `demo.txt` and transmits after edits.

## Protocol

| Symbol | Frequency |
| --- | ---: |
| Sync | 17,500 Hz |
| Bit 0 | 18,000 Hz |
| Bit 1 | 19,000 Hz |
| Bit duration | 100 ms |
| Tolerance | +/- 250 Hz |

Audible debug mode uses 1,000 Hz, 2,000 Hz, and 1,500 Hz sync so you can prove the code path works before moving into the ultrasonic range.
