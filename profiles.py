from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrequencyProfile:
    name: str
    description: str
    freq_zero: float
    freq_one: float
    sync_freq: float
    tolerance: float
    bit_duration: float
    repeat_bits: int = 1


PROFILES: dict[str, FrequencyProfile] = {
    "reliable": FrequencyProfile(
        name="reliable",
        description="Validated laptop profile: audible/near-ultrasonic 10-12 kHz.",
        freq_zero=10_000.0,
        freq_one=12_000.0,
        sync_freq=11_000.0,
        tolerance=700.0,
        bit_duration=0.1,
    ),
    "reliable_slow": FrequencyProfile(
        name="reliable_slow",
        description="Validated profile with repetition for clean demo.txt decoding.",
        freq_zero=10_000.0,
        freq_one=12_000.0,
        sync_freq=11_000.0,
        tolerance=700.0,
        bit_duration=0.15,
        repeat_bits=3,
    ),
    "proposal": FrequencyProfile(
        name="proposal",
        description="Proposal ultrasonic profile: 18-19 kHz. Hardware dependent.",
        freq_zero=18_000.0,
        freq_one=19_000.0,
        sync_freq=17_500.0,
        tolerance=700.0,
        bit_duration=0.1,
    ),
    "near_ultra": FrequencyProfile(
        name="near_ultra",
        description="Lower near-ultrasonic fallback for hardware that filters 18-19 kHz.",
        freq_zero=17_000.0,
        freq_one=18_000.0,
        sync_freq=16_500.0,
        tolerance=700.0,
        bit_duration=0.1,
    ),
}


def add_profile_argument(parser) -> None:
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        help="Use a named frequency profile. Explicit frequency/timing flags override profile values.",
    )


def apply_profile(args) -> None:
    if not getattr(args, "profile", None):
        return

    profile = PROFILES[args.profile]
    for attr in ("freq_zero", "freq_one", "sync_freq", "tolerance", "bit_duration"):
        if getattr(args, attr, None) is None:
            setattr(args, attr, getattr(profile, attr))

    if getattr(args, "repeat_bits", 1) == 1 and profile.repeat_bits != 1:
        args.repeat_bits = profile.repeat_bits


def estimate_seconds(chars: int, bit_duration: float, repeat_bits: int) -> float:
    sync_symbols = 16
    return (sync_symbols + chars * 8 * repeat_bits) * bit_duration
