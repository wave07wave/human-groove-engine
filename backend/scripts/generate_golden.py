import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.optimizer import generate_candidates
from app.midi.exporter import export_midi
from app.models.meter import MeterDefinition
from app.presets import get_preset

CASES = {
    "balanced-100": ("Balanced", 100, 1001),
    "funk-105": ("Funk", 105, 1002),
    "laid-back-86": ("Laid Back", 86, 1003),
    "hypnotic-124": ("Hypnotic", 124, 1004),
    "broken-132": ("Broken", 132, 1005),
    "minimal-118": ("Minimal", 118, 1006),
}


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "golden"
    destination.mkdir(exist_ok=True)
    index = []
    for slug, (preset, bpm, seed) in CASES.items():
        candidates = generate_candidates(
            bpm=bpm,
            bars=8,
            meter=MeterDefinition.from_name("4/4"),
            intent=get_preset(preset),
            seed=seed,
            count=4,
            mode="preview",
            preset=preset,
        )
        case = destination / slug
        case.mkdir(exist_ok=True)
        for number, pattern in enumerate(candidates, start=1):
            midi_name = f"candidate-{number}.mid"
            (case / midi_name).write_bytes(export_midi(pattern))
            record = {
                "schema_version": pattern.metadata.schema_version,
                "preset": preset,
                "bpm": bpm,
                "bars": 8,
                "seed": seed,
                "candidate": number,
                "pattern_id": pattern.pattern_id,
                "target_dna": pattern.intent.target_dna.model_dump(),
                "measured_dna": pattern.analysis.measured_dna.model_dump(),
                "listener": pattern.analysis.listener.model_dump(),
                "midi": midi_name,
            }
            (case / f"candidate-{number}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            index.append({"case": slug, **record})
    (destination / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Generated {len(index)} golden candidates in {destination}")


if __name__ == "__main__":
    main()
