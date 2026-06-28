from __future__ import annotations

import json
from pathlib import Path

from agentimmune_data.cli import build_sft, build_sft_traces, validate_split
from agentimmune.sample_data import sample_split


def test_validate_split_accepts_unseen_held_out_family(tmp_path: Path) -> None:
    path = tmp_path / "split.json"
    path.write_text(
        json.dumps(
            {
                "train": [{"attack_id": "a1", "family": "ad_break_splice", "seed": "1"}],
                "dev": [],
                "held_out": [{"attack_id": "a2", "family": "cross_lingual", "seed": "2"}],
                "benign": [],
            }
        )
    )

    assert validate_split(path) == 0


def test_validate_split_accepts_id_only_variant_holdout(tmp_path: Path) -> None:
    path = tmp_path / "split.json"
    path.write_text(
        json.dumps(
            {
                "train": ["l0_ad_break_splice_seed_244"],
                "dev": ["l1_ad_break_splice_seed_230"],
                "held_out": ["l1_spoofed_host_directive_seed_752"],
                "novel_held_out": [],
                "benign": ["run_clean_fed_sample_001"],
            }
        )
    )

    assert validate_split(path) == 0


def test_validate_split_rejects_attack_id_leakage(tmp_path: Path) -> None:
    path = tmp_path / "split.json"
    path.write_text(
        json.dumps(
            {
                "train": [{"attack_id": "a1", "family": "ad_break_splice", "seed": "1"}],
                "dev": [],
                "held_out": [{"attack_id": "a1", "family": "cross_lingual", "seed": "2"}],
                "benign": [],
            }
        )
    )

    assert validate_split(path) == 1


def test_build_sft_writes_training_jsonl(tmp_path: Path) -> None:
    split = sample_split()
    split_path = tmp_path / "split.json"
    out = tmp_path / "sft.jsonl"
    split_path.write_text(json.dumps(split))

    assert build_sft(split_path, out, [], None, allow_missing=False) == 0
    lines = out.read_text().splitlines()
    assert len(lines) == 2
    payload = json.loads(lines[0])
    assert payload["messages"][0]["role"] == "system"
    assert "verdict" in payload["messages"][2]["content"]


def test_build_sft_reports_missing_id_split(tmp_path: Path) -> None:
    split_path = tmp_path / "split.json"
    out = tmp_path / "sft.jsonl"
    split_path.write_text(
        json.dumps(
            {
                "train": ["missing_attack"],
                "dev": [],
                "held_out": [],
                "benign": [],
            }
        )
    )

    assert build_sft(split_path, out, [str(tmp_path / "*.json")], None, allow_missing=False) == 1


def test_build_sft_resolves_trace_lookup(tmp_path: Path) -> None:
    split = sample_split()
    trace_path = tmp_path / "labeled_trace.json"
    lookup_path = tmp_path / "trace_lookup.json"
    split_path = tmp_path / "split.json"
    out = tmp_path / "sft.jsonl"

    trace_path.write_text(json.dumps(split["train"][0]))
    lookup_path.write_text(json.dumps({"atk_train_1": str(trace_path)}))
    split_path.write_text(
        json.dumps(
            {
                "train": ["atk_train_1"],
                "dev": [],
                "held_out": [],
                "benign": [],
            }
        )
    )

    assert build_sft(split_path, out, [], lookup_path, allow_missing=False) == 0
    assert len(out.read_text().splitlines()) == 1


def test_build_sft_traces_writes_real_trace_examples(tmp_path: Path) -> None:
    split = sample_split()
    trace_path = tmp_path / "trace.json"
    out = tmp_path / "sft_traces.jsonl"
    trace_path.write_text(json.dumps(split["held_out"][0]))

    assert build_sft_traces([str(trace_path)], out) == 0
    assert len(out.read_text().splitlines()) == 1
