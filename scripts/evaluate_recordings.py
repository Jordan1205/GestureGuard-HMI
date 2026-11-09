"""Compare unchanged MediaPipe scores, original gating and improved temporal evidence."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from gestureguard.learning import evaluate_recordings, load_recordings
from gestureguard.domain import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recordings", type=Path, default=ROOT / "data" / "recordings")
    parser.add_argument("--held-out-groups", help="Comma-separated untouched participant/session IDs.")
    parser.add_argument("--group-by", choices=("participant_id", "session_id"), default="participant_id")
    parser.add_argument("--model", type=Path, help="Optional numeric JSON forest generated locally by train_classifier.py.")
    parser.add_argument("--settings", type=Path, help="Frozen settings JSON; defaults are recorded in the report if omitted.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "evaluation" / "recognition-report.json")
    args = parser.parse_args()
    try:
        artifact = json.loads(args.model.read_text(encoding="utf-8")) if args.model else None
        settings = Settings(**json.loads(args.settings.read_text(encoding="utf-8"))) if args.settings else None
        report = evaluate_recordings(load_recordings(args.recordings),
            {x.strip() for x in args.held_out_groups.split(",") if x.strip()} if args.held_out_groups else None,
            args.group_by, artifact, settings)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "samples": report["samples"], "report": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
