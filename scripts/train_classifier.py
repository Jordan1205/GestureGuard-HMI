"""Train an optional local numerical-JSON Random Forest after collecting real data."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from gestureguard.learning import load_recordings, train_experiment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recordings", type=Path, default=ROOT / "data" / "recordings")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "models" / "forest-experiment.json")
    parser.add_argument("--group-by", choices=("participant_id", "session_id"), default="participant_id")
    parser.add_argument("--allow-session-split", action="store_true", help="Acknowledge this does not establish cross-person generalization.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.group_by == "session_id" and not args.allow_session_split:
        parser.error("Session grouping requires --allow-session-split; collect independent recording occasions.")
    try:
        artifact, report = train_experiment(load_recordings(args.recordings), args.group_by, args.seed)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, allow_nan=False), encoding="utf-8")
    report_path = args.output.with_name(args.output.stem + "-report.json")
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "model": str(args.output), "report": str(report_path)}, indent=2))


if __name__ == "__main__":
    main()
