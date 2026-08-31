import os
from pathlib import Path

PPQ = 960
ENGINE_VERSION = "0.11.0"
ANALYSIS_VERSION = "1.5"
SCHEMA_VERSION = "1.0"
PRESET_VERSION = "1.1"
RNG_ALGORITHM = "PCG64DXSM/SHA-256"
PERFORMANCE_MODEL_PATH = Path(
    os.environ.get(
        "HGE_PERFORMANCE_MODEL_PATH",
        Path(__file__).resolve().parent / "engine" / "models" / "gmd-performance-v1.json",
    )
)
DATABASE_PATH = Path(
    os.environ.get("HGE_DATABASE_PATH", Path(__file__).resolve().parents[1] / "human_groove.db")
)
MAX_MICROTIMING_US = 25_000

INSTRUMENTS = ("kick", "snare", "closed_hat", "open_hat", "percussion", "bass")
DRUM_PITCHES = {"kick": 36, "snare": 38, "closed_hat": 42, "open_hat": 46, "percussion": 39}
INSTRUMENT_OFFSETS_US = {
    "kick": 0,
    "snare": 7_000,
    "closed_hat": -3_000,
    "open_hat": -2_000,
    "percussion": 2_000,
    "bass": 5_000,
}
