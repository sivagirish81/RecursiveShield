# AgentImmune / Recursive Shield

Shared spine for the hackathon system: contracts, oracle stubs, guardrail stubs, eval harness, and later the fine-tune/eval/promote pipeline.

## D1 smoke test

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/smoke_d1.py
pytest
```

The pure D1 scaffold was also smoke-tested locally on Python 3.12.8, but team stack lock remains Python 3.11.

Teammate branches can import either:

```python
from agentimmune.contracts import Trace, AttackSpec
```

or the short compatibility import:

```python
from contracts import Trace, AttackSpec
```

## D2 dry-run

```bash
python scripts/run_d2_dryrun.py
```

This uses stub training plus the stub guardrail, then writes local stand-ins for Atlas collections:

- `artifacts/local_store/model_versions.jsonl`
- `artifacts/local_store/eval_runs.jsonl`

## D3 stub serving and capture

```bash
pip install -e ".[serving]"
uvicorn agentimmune.server:app --host 0.0.0.0 --port 8000
python scripts/capture_demo_stub.py
```

`/classify` accepts the same guardrail payload A will call before `confirm_order`:

```json
{
  "audio_path": "artifacts/audio/poisoned.wav",
  "screenshot_path": "artifacts/screens/order.png",
  "action": {"tool": "confirm_order", "args": {}},
  "policy": {"raw_text": "max 5%", "max_position_pct": 5}
}
```

`/classify-payload` accepts A's full `GuardrailHookPayload` shape:

```json
{
  "run_id": "run_l1",
  "audio_path": "artifacts/audio/poisoned.wav",
  "screenshot_path": "artifacts/screens/order.png",
  "transcript_window": "recent transcript text",
  "proposed_action": {"tool": "confirm_order", "args": {}},
  "policy": {"raw_text": "max 5%", "max_position_pct": 5},
  "recent_actions": [],
  "metadata": {}
}
```

## GPU training box

On Lightning AI / Colab GPU:

```bash
pip install -e ".[dev,mongo,voyage,google]"
pip install -r requirements/gpu-training.txt
```

Do not install `requirements/gpu-training.txt` on local Mac unless you specifically want to debug dependency resolution.
