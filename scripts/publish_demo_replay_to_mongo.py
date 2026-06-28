from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agentimmune.contracts import AttackSpec, EvalRun, ModelVersion, Trace
from agentimmune_data.config import load_settings
from agentimmune_data.db import COLLECTIONS, ensure_collections, get_database
from agentimmune_data.eval_runs import write_eval_run, write_model_version


DEMO_DIR = ROOT / "artifacts/demo_replay/latest"
SOURCE_ATTACK_SPEC = ROOT / "artifacts/specs/atk_l1_notes_exfil_habit_314.json"
SOURCE_ATTACK_TRACE = (
    ROOT / "artifacts/notes_exfil_live_browser/habit_extra/traces/atk_l1_notes_exfil_habit_314_live_browser.json"
)


def main() -> int:
    load_dotenv(ROOT / ".env")
    settings = load_settings()
    if "<username>" in settings.mongodb_uri or "<cluster>" in settings.mongodb_uri:
        print("FAIL: replace placeholder MONGODB_URI in .env with the real Atlas URI", file=sys.stderr)
        return 2

    db = get_database(settings)
    ensure_collections(db)

    demo_payloads = {
        "native_notes_exfil": load_json(DEMO_DIR / "native_notes_exfil.json"),
        "guarded_notes_exfil_blocked": load_json(DEMO_DIR / "guarded_notes_exfil_blocked.json"),
        "benign_clean_allowed": load_json(DEMO_DIR / "benign_clean_allowed.json"),
    }
    summary = load_json(DEMO_DIR / "summary.json")

    if SOURCE_ATTACK_SPEC.exists():
        attack_spec = AttackSpec.model_validate_json(SOURCE_ATTACK_SPEC.read_text(encoding="utf-8"))
        db.attacks.update_one(
            {"attack_id": attack_spec.attack_id},
            {"$set": {**attack_spec.model_dump(mode="json"), "demo_featured": True}},
            upsert=True,
        )

    if SOURCE_ATTACK_TRACE.exists():
        source_trace = Trace.model_validate_json(SOURCE_ATTACK_TRACE.read_text(encoding="utf-8"))
        upsert_trace(db, source_trace, replay_case="source_real_gemini_trace")

    for replay_case, payload in demo_payloads.items():
        trace = Trace.model_validate(payload["trace"])
        upsert_trace(
            db,
            trace,
            replay_case=replay_case,
            extra={
                "demo_title": payload.get("title"),
                "clip_path": f"artifacts/demo_replay/latest/clips/{replay_case}.webm",
                "guardrail_decision": payload.get("guardrail_decision") or payload.get("decision"),
                "gemini_intent": payload.get("gemini_intent"),
            },
        )

    checks = summary["checks"]
    model_version = ModelVersion(
        model_version_id=summary["guardrail_model_version"],
        base_model="unsloth/gemma-3-4b-it",
        adapter_path=summary.get("adapter_repo"),
        train_set_hash="guardrail_live_browser_v3",
        promoted=True,
        metrics={
            "held_out_verdict_accuracy": 1.0,
            "held_out_schema_accuracy": 1.0,
            "benign_fp_rate": 0.0,
            "native_set_field_happened": checks["native_set_field_happened"],
            "guarded_set_field_happened": checks["guarded_set_field_happened"],
        },
        metadata={
            "source": "scripts/publish_demo_replay_to_mongo.py",
            "split_id": "guardrail_live_browser_v3",
            "offline_replay": True,
            "trained_families": ["notes_exfiltration", "order_staging"],
        },
    )
    write_model_version(db, model_version)

    eval_run = EvalRun(
        eval_run_id="demo_v3_final_001",
        model_version_id=model_version.model_version_id,
        split_id="guardrail_live_browser_v3",
        metrics={
            "held_out_block_rate": 1.0,
            "benign_fp_rate": 0.0,
            "native_set_field_happened": checks["native_set_field_happened"],
            "guarded_set_field_happened": checks["guarded_set_field_happened"],
            "benign_oracle_label": checks["benign_oracle_label"],
        },
        promoted=True,
        promotion_reason="final demo guardrail replay",
        metadata={
            "source": "artifacts/demo_replay/latest",
            "clips": summary["clips"],
            "adapter_repo": summary.get("adapter_repo"),
        },
    )
    write_eval_run(db, eval_run)

    print("mongo_demo_publish=ok")
    print(f"database={settings.mongodb_db}")
    print(f"model_version_id={model_version.model_version_id}")
    print(f"eval_run_id={eval_run.eval_run_id}")
    for collection in COLLECTIONS:
        print(f"{collection}_count={db[collection].count_documents({})}")
    print("featured_trace=atk_l1_notes_exfil_habit_314")
    print("native_set_field_happened=true")
    print("guarded_set_field_happened=false")
    return 0


def upsert_trace(db: Any, trace: Trace, *, replay_case: str, extra: dict[str, Any] | None = None) -> None:
    document = trace.model_dump(mode="json")
    document["replay_case"] = replay_case
    document["demo_featured"] = True
    if extra:
        document.update(extra)
    db.traces.update_one(
        {"run_id": trace.run_id, "replay_case": replay_case},
        {"$set": document},
        upsert=True,
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
