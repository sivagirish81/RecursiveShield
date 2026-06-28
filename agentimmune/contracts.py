from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class OracleVerdict(StrEnum):
    SAFE = "safe"
    UNSAFE = "unsafe"


class ActionVerdict(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    BLOCK = "block"


class NativeDefenseOutcome(StrEnum):
    CAUGHT = "caught"
    BYPASSED = "bypassed"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class SplitName(StrEnum):
    TRAIN = "train"
    DEV = "dev"
    HELD_OUT = "held_out"
    BENIGN = "benign"


class AttackFamily(StrEnum):
    SPOOFED_HOST_DIRECTIVE = "spoofed_host_directive"
    FAKE_BREAKING_NEWS_URGENCY = "fake_breaking_news_urgency"
    AD_BREAK_SPLICE = "ad_break_splice"
    AUTHORITY_IMPERSONATION = "authority_impersonation"
    TOOL_TRIGGER_PAYWALL = "tool_trigger_paywall"
    MEMORY_EXFILTRATION = "memory_exfiltration"
    CONSTRAINT_OVERRIDE = "constraint_override"
    MISREPORT = "misreport"
    MULTI_STEP_DELAYED = "multi_step_delayed"
    CROSS_LINGUAL = "cross_lingual"
    HOMOPHONE_OBFUSCATION = "homophone_obfuscation"
    SUB_AUDIBLE_OVER_SPOKEN = "sub_audible_over_spoken"


class Constraint(StrictModel):
    policy_id: str = Field(default_factory=lambda: f"pol_{uuid4().hex[:12]}")
    raw_text: str
    max_position_pct: float = Field(gt=0, le=100)
    allowed_universe: Literal["large_caps", "all"] = "large_caps"
    require_user_confirmation: bool = True
    forbid_unverified_tips: bool = True
    allowed_symbols: list[str] = Field(default_factory=list)
    forbidden_symbols: list[str] = Field(default_factory=list)
    min_market_cap_usd: float | None = Field(default=10_000_000_000, ge=0)
    notes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("allowed_symbols", "forbidden_symbols")
    @classmethod
    def normalize_symbols(cls, symbols: list[str]) -> list[str]:
        return [symbol.upper().lstrip("$") for symbol in symbols]


class ToolAction(StrictModel):
    tool: Literal["place_order", "confirm_order", "read_portfolio", "set_field"]
    args: dict[str, Any] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=utc_now)
    intent: str | None = None
    screenshot_path: str | None = None


class OracleLabel(StrictModel):
    label: OracleVerdict
    violated_constraints: list[str] = Field(default_factory=list)
    forbidden_tool_fired: bool = False
    induced_by_injection: bool = False
    native_defense_outcome: NativeDefenseOutcome = NativeDefenseOutcome.UNKNOWN
    reason: str = ""


class Trace(StrictModel):
    run_id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    attack_id: str | None = None
    clean_baseline_run_id: str | None = None
    audio_path: str
    transcript: str
    policy: Constraint
    actions: list[ToolAction] = Field(default_factory=list)
    final_action: ToolAction | None = None
    native_defense_outcome: NativeDefenseOutcome = NativeDefenseOutcome.UNKNOWN
    oracle: OracleLabel | None = None
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AttackSpec(StrictModel):
    attack_id: str = Field(default_factory=lambda: f"atk_{uuid4().hex[:12]}")
    family: AttackFamily
    payload_text: str = Field(min_length=1)
    delivery: str = Field(min_length=1)
    target_violation: str = Field(min_length=1)
    audio_path: str
    seed: str
    source_transcript_id: str
    clean_audio_path: str | None = None
    splice_start_sec: float | None = Field(default=None, ge=0)
    generator: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("audio_path", "clean_audio_path")
    @classmethod
    def normalize_paths(cls, path: str | None) -> str | None:
        if path is None:
            return None
        return str(Path(path.replace("\\", "/")))


class SplitAssignment(StrictModel):
    split_id: str = Field(default_factory=lambda: f"split_{uuid4().hex[:12]}")
    attack_id: str
    family: AttackFamily
    seed: str
    split: SplitName
    split_hash: str
    is_held_out_family: bool = False
    leakage_checked: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelVersion(StrictModel):
    model_version_id: str = Field(default_factory=lambda: f"model_{uuid4().hex[:12]}")
    parent_version_id: str | None = None
    base_model: str = "unsloth/gemma-4-E4B-it"
    adapter_path: str | None = None
    train_set_hash: str
    promoted: bool = False
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalRun(StrictModel):
    eval_run_id: str = Field(default_factory=lambda: f"eval_{uuid4().hex[:12]}")
    model_version_id: str
    split_id: str
    metrics: dict[str, Any]
    promoted: bool = False
    promotion_reason: str
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GuardrailDecision(StrictModel):
    verdict: ActionVerdict
    reason: str
    violated_constraints: list[str] = Field(default_factory=list)
    model_version_id: str = "stub-v0"
    latency_ms: float | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GuardrailHookPayload(StrictModel):
    """Request body A sends before executing a state-changing brokerage action."""

    run_id: str
    audio_path: str
    screenshot_path: str | None = None
    transcript_window: str = ""
    proposed_action: ToolAction
    policy: Constraint
    recent_actions: list[ToolAction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
