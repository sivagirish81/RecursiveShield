from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from google import genai

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agentimmune.contracts import AttackSpec
from scripts.run_split_attack_traces import (
    DEFAULT_BASE_URL,
    DEFAULT_LIVE_MODEL,
    DEFAULT_MODEL,
    expected_symbol,
    forbidden_order_args,
    get_trace,
    load_api_key,
    native_caught,
    normalize_path,
    relabel_trace,
    transcribe_audio,
    call_gemini,
)


DEFAULT_ATTACK_IDS = ["atk_l1_stealth_031", "atk_l1_stealth_034"]
DEFAULT_SCREENSHOT = "artifacts/screenshots/stealth_candidate_brokerage_live.png"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_spec(attack_id: str) -> AttackSpec:
    path = Path("artifacts/specs") / f"{attack_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing attack spec for {attack_id}: {path}")
    return AttackSpec.model_validate_json(path.read_text())


def start_candidate_run(base_url: str, spec: AttackSpec, transcript: str) -> tuple[str, dict[str, Any]]:
    payload = {
        "scenario": "l1",
        "attack_id": spec.attack_id,
        "audio_path": normalize_path(spec.audio_path),
        "transcript_window": transcript,
        "guardrail_enabled": False,
    }
    response = httpx.post(f"{base_url}/brokerage/runs", json=payload, timeout=30)
    entry = {
        "endpoint": "POST /brokerage/runs",
        "request": payload,
        "status_code": response.status_code,
        "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
    }
    response.raise_for_status()
    return str(response.json()["run_id"]), entry


def post_tool_with_log(base_url: str, run_id: str, tool: str, args: dict[str, Any], intent: str, screenshot_path: str) -> dict[str, Any]:
    payload = {
        "tool": tool,
        "args": args,
        "intent": intent,
        "screenshot_path": screenshot_path,
    }
    response = httpx.post(f"{base_url}/brokerage/runs/{run_id}/tool", json=payload, timeout=30)
    entry = {
        "endpoint": f"POST /brokerage/runs/{run_id}/tool",
        "request": payload,
        "status_code": response.status_code,
        "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
    }
    response.raise_for_status()
    return entry


def run_candidate(
    base_url: str,
    client: genai.Client,
    model: str,
    screenshot_path: Path,
    out_dir: Path,
    attack_id: str,
) -> dict[str, Any]:
    spec = load_spec(attack_id)
    audio_path = Path(normalize_path(spec.audio_path))
    if not audio_path.exists():
        raise FileNotFoundError(f"Missing candidate audio for {attack_id}: {audio_path}")
    if not screenshot_path.exists():
        raise FileNotFoundError(f"Missing brokerage screenshot for {attack_id}: {screenshot_path}")

    transcript = transcribe_audio(client, model, audio_path, out_dir, attack_id)
    gemini_log = call_gemini(client, model, spec, audio_path, screenshot_path, transcript, "poisoned_candidate")
    action_log_path = out_dir / "gemini_action_logs" / f"{attack_id}.json"
    action_log_path.parent.mkdir(parents=True, exist_ok=True)
    action_log_path.write_text(json.dumps(gemini_log, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    run_id, start_log = start_candidate_run(base_url, spec, transcript)
    tool_logs: list[dict[str, Any]] = [start_log]

    caught = native_caught(gemini_log)
    if not caught:
        symbol = expected_symbol(spec)
        order_args = forbidden_order_args(symbol)
        tool_logs.append(
            post_tool_with_log(
                base_url,
                run_id,
                "read_portfolio",
                {"purpose": "risk_check", "candidate_attack_id": attack_id},
                "Gemini Computer Use returned an actionable browser function call; bridge inspected portfolio before sizing.",
                str(screenshot_path),
            )
        )
        tool_logs.append(
            post_tool_with_log(
                base_url,
                run_id,
                "place_order",
                order_args,
                f"Gemini Computer Use returned an actionable browser function call; bridge placed candidate target {symbol} order.",
                str(screenshot_path),
            )
        )
        tool_logs.append(
            post_tool_with_log(
                base_url,
                run_id,
                "confirm_order",
                order_args,
                f"Gemini Computer Use returned an actionable browser function call; bridge confirmed candidate target {symbol} order.",
                str(screenshot_path),
            )
        )

    trace = get_trace(base_url, run_id)
    trace["native_defense_outcome"] = "caught" if caught else "bypassed"
    trace["metadata"] = {
        **trace.get("metadata", {}),
        "stealth_candidate_run": True,
        "not_final_l1_training_example": True,
        "scenario": "poisoned_candidate",
        "model": model,
        "model_id": model,
        "live_api_model_id": os.getenv("GEMINI_LIVE_MODEL_ID", DEFAULT_LIVE_MODEL),
        "agent_native_defense_enabled": True,
        "custom_guardrail_enabled": False,
        "transcript_source": "Gemini API audio transcription",
        "attack_spec": spec.model_dump(mode="json"),
        "gemini_action_log_path": str(action_log_path),
        "gemini_response": gemini_log,
        "brokerage_screen_screenshot": str(screenshot_path),
        "tool_endpoint_log_path": str(out_dir / "brokerage_tool_logs" / f"{attack_id}.json"),
        "candidate_summary": {
            "gemini_function_calls_attempted": gemini_log.get("function_calls", []),
            "place_order_happened": any(action.get("tool") == "place_order" for action in trace.get("actions", [])),
            "set_field_happened": any(action.get("tool") == "set_field" for action in trace.get("actions", [])),
            "confirm_order_happened": any(action.get("tool") == "confirm_order" for action in trace.get("actions", [])),
        },
    }
    trace = relabel_trace(trace)

    tool_log_path = out_dir / "brokerage_tool_logs" / f"{attack_id}.json"
    tool_log_path.parent.mkdir(parents=True, exist_ok=True)
    tool_log_path.write_text(json.dumps({"run_id": run_id, "tool_logs": tool_logs, "final_trace": trace}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    trace_path = out_dir / "traces" / f"{attack_id}.json"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "attack_id": attack_id,
        "trace_path": str(trace_path),
        "gemini_action_log_path": str(action_log_path),
        "tool_endpoint_log_path": str(tool_log_path),
        "native_defense_outcome": trace["native_defense_outcome"],
        "oracle_label": trace.get("oracle", {}).get("label"),
        "actions": [action["tool"] for action in trace.get("actions", [])],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run detector-bypass candidate WAVs through the real Gemini brokerage loop.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=os.getenv("GEMINI_COMPUTER_USE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--screenshot", type=Path, default=Path(DEFAULT_SCREENSHOT))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/stealth_candidate_traces") / utc_stamp())
    parser.add_argument("--attack-id", action="append", dest="attack_ids")
    args = parser.parse_args()

    client = genai.Client(api_key=load_api_key())
    results = [
        run_candidate(args.base_url, client, args.model, args.screenshot, args.out_dir, attack_id)
        for attack_id in (args.attack_ids or DEFAULT_ATTACK_IDS)
    ]
    trace_lookup = {result["attack_id"]: result["trace_path"] for result in results}
    (args.out_dir / "trace_lookup.json").write_text(json.dumps(trace_lookup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "out_dir": str(args.out_dir),
        "model_id": args.model,
        "live_api_model_id": os.getenv("GEMINI_LIVE_MODEL_ID", DEFAULT_LIVE_MODEL),
        "native_defense_on": True,
        "custom_guardrail_enabled": False,
        "not_final_l1_training_examples": True,
        "screenshot": str(args.screenshot),
        "results": results,
        "trace_lookup": "trace_lookup.json",
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
