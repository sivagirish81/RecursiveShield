from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agentimmune.contracts import Trace
from agentimmune_data.cli import trace_to_sft_example


DEFAULT_SUMMARY = Path("artifacts/notes_exfil_live_browser/consolidated_summary.json")
DEFAULT_OUT_DIR = Path("artifacts/training/notes_exfil_splits")
DEFAULT_TRACE_GLOBS = [
    "artifacts/notes_exfil_live_browser/*/traces/*_live_browser.json",
    "artifacts/notes_exfil_live_browser/*/benign_traces/*.json",
]


def load_trace(path: str) -> Trace:
    return Trace.model_validate_json(Path(path).read_text(encoding="utf-8"))


def split_ids(items: list[str], train_n: int, dev_n: int) -> dict[str, list[str]]:
    ordered = sorted(items)
    return {
        "train": ordered[:train_n],
        "dev": ordered[train_n : train_n + dev_n],
        "held_out": ordered[train_n + dev_n :],
    }


def split_counts(total: int) -> tuple[int, int]:
    if total <= 2:
        return max(1, total), 0
    train_n = max(1, int(total * 0.7))
    remaining = total - train_n
    dev_n = max(1, remaining // 2)
    if train_n + dev_n >= total:
        dev_n = max(0, total - train_n - 1)
    return train_n, dev_n


def write_jsonl(path: Path, traces: list[Trace]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(json.dumps(trace_to_sft_example(trace), sort_keys=True) + "\n")


def is_kept_unsafe(trace: Trace) -> bool:
    return (
        trace.attack_id is not None
        and trace.native_defense_outcome == "bypassed"
        and trace.oracle is not None
        and trace.oracle.label == "unsafe"
        and any(action.tool == "set_field" for action in trace.actions)
    )


def is_kept_benign(trace: Trace) -> bool:
    return trace.attack_id is None and trace.oracle is not None and trace.oracle.label == "safe"


def merge_trace_globs(unsafe_lookup: dict[str, str], benign_lookup: dict[str, str], patterns: list[str]) -> None:
    import glob

    for pattern in patterns:
        for raw_path in sorted(glob.glob(pattern)):
            path = Path(raw_path)
            try:
                trace = load_trace(path.as_posix())
            except Exception:
                continue
            if is_kept_unsafe(trace):
                unsafe_lookup[trace.attack_id or trace.run_id] = path.as_posix()
            elif is_kept_benign(trace):
                benign_lookup[trace.run_id] = path.as_posix()


def build(summary_path: Path, out_dir: Path, trace_globs: list[str]) -> dict[str, Any]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    unsafe_lookup: dict[str, str] = dict(summary["trace_lookup"])
    benign_lookup: dict[str, str] = {
        item["run_id"]: item["trace_path"] for item in summary.get("benign_traces", [])
    }
    merge_trace_globs(unsafe_lookup, benign_lookup, trace_globs)

    unsafe_train_n, unsafe_dev_n = split_counts(len(unsafe_lookup))
    benign_train_n, benign_dev_n = split_counts(len(benign_lookup))
    unsafe_split = split_ids(list(unsafe_lookup), train_n=unsafe_train_n, dev_n=unsafe_dev_n)
    benign_split = split_ids(list(benign_lookup), train_n=benign_train_n, dev_n=benign_dev_n)

    split = {
        "id": "notes_exfil_live_browser_v1",
        "notes": (
            "Same-family split over real live-browser notes-exfil bypass traces. "
            "This is sufficient for a first guardrail LoRA smoke run, but not a novel-family final eval."
        ),
        "train": unsafe_split["train"],
        "dev": unsafe_split["dev"],
        "held_out": unsafe_split["held_out"],
        "novel_held_out": [],
        "benign_train": benign_split["train"],
        "benign_dev": benign_split["dev"],
        "benign_held_out": benign_split["held_out"],
    }

    lookup = {**unsafe_lookup, **benign_lookup}
    trace_lookup_path = out_dir / "trace_lookup.json"
    split_path = out_dir / "split_manifest.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_lookup_path.write_text(json.dumps(lookup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    split_path.write_text(json.dumps(split, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    traces_by_split: dict[str, list[Trace]] = {}
    for name, ids in [
        ("train", split["train"] + split["benign_train"]),
        ("dev", split["dev"] + split["benign_dev"]),
        ("held_out", split["held_out"] + split["benign_held_out"]),
    ]:
        traces_by_split[name] = [load_trace(lookup[item]) for item in ids]
        write_jsonl(out_dir / f"{name}.jsonl", traces_by_split[name])

    report = {
        "split_manifest": split_path.as_posix(),
        "trace_lookup": trace_lookup_path.as_posix(),
        "train_examples": len(traces_by_split["train"]),
        "dev_examples": len(traces_by_split["dev"]),
        "held_out_examples": len(traces_by_split["held_out"]),
        "unsafe_train": len(split["train"]),
        "unsafe_dev": len(split["dev"]),
        "unsafe_held_out": len(split["held_out"]),
        "benign_train": len(split["benign_train"]),
        "benign_dev": len(split["benign_dev"]),
        "benign_held_out": len(split["benign_held_out"]),
        "warning": "held_out is same-family only; keep novel family eval separate when new real bypass traces arrive.",
    }
    (out_dir / "split_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--trace-glob", action="append", default=DEFAULT_TRACE_GLOBS)
    args = parser.parse_args()
    report = build(Path(args.summary), Path(args.out_dir), args.trace_glob)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
