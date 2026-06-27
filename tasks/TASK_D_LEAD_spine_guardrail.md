# TASK D (LEAD) — Spine, Starter Code, Guardrail Fine-Tune
**Owner:** You (lead) · **Branch:** `main` + `feat/spine` · **Owns:** INV-4 + Push Gate "Guardrail fine-tune" + integration
**Read first:** `PROJECT.md`. You own `main`, the **interface contracts**, the **orchestration spine**, and the **guardrail fine-tune (final task)**. Front-load the scaffold so A/B/C are unblocked in the first hour; save your heavy lift (the fine-tune + exhaustive eval) for when their data lands. Keep your own load sane — scaffolding and orchestration are write-once; the fine-tune is the focused finish.

## STACK LOCK (you author this block; it is identical in all 4 files)
- Python **3.11**. Gemini SDK `google-genai >= 2.3.0`. Guardrail base **`unsloth/gemma-4-E4B-it`** (audio-capable); optional hero-final `unsloth/gemma-4-12b-it`.
- Fine-tune: **Unsloth** + LoRA — `load_in_4bit=True`, `use_gradient_checkpointing="unsloth"`, bf16, rank 16–32, 1–3 epochs. Let Unsloth pin torch/transformers/trl/peft — **don't hand-pin them.**
- Serving: **vLLM** (latest stable). GPU: **Lightning AI 80GB** (primary), Colab Pro (backup/parallel).
- Memory: MongoDB Atlas DB `agentimmune` (cluster from C); embeddings **Voyage** (`voyage-3.5` or current).
- **Sponsors you touch:** Google (Gemma 4 — the $5K core), DigitalOcean (vLLM serving host).

---

### D1 — Repo scaffold + interface contracts + STARTER CODE (unblocks everyone — do first)
Build: repo skeleton, the **pydantic contracts** every branch imports (`Constraint`, `Trace`, `OracleLabel`, `AttackSpec`, `SplitAssignment`, `ModelVersion`), and **runnable stubs**: an oracle stub, a **guardrail-inference stub** (`classify(audio, screenshot, action, policy) → {verdict, reason}` returning canned outputs), and the eval-harness skeleton. This is the "solid start" you hand the team.
**Eval (must pass):**
- A/B/C can `import contracts` and run against the stubs **before** real components exist (each confirms in their `ASSUMPTIONS.md`).
- Contract change = one PR to `main` that all branches pull; no divergent local copies (grep check).
- The guardrail stub honors the same I/O signature the real model will, so A's interception point doesn't change later.

### D2 — Orchestration spine: fine-tune → eval → promote
Build: the pipeline that pulls C's `split.json`, trains a round, runs the eval, and **promotes only if the gate passes**; writes `model_versions` + `eval_runs` to Atlas.
**Eval (must pass):**
- Dry-run on stub data executes round → eval → promote/reject end-to-end with **zero manual steps**.
- The promote gate **refuses** a checkpoint that regresses benign FP (feed it a deliberately bad one → rejected).
- Every promoted version is reproducible from its `train_set_hash` (logged).

### D3 — vLLM serving + demo capture (offline replay)
Build: serve the promoted LoRA checkpoint via vLLM behind the same signature as the stub; a capture harness that records every demo run to artifacts for **offline** replay.
**Eval (must pass):**
- Swap stub → real served model with **no code change** in A's interception point.
- End-to-end classify on one real trace within the demo latency budget (record the number).
- Full 0:00–2:30 demo replays **offline** from artifacts, 3/3, no live calls.

### D4 — GUARDRAIL FINE-TUNE (your final major task — test everything)
Build: Unsloth LoRA on **Gemma-4 E4B** (audio-native; transcript-text fallback ready if audio SFT is too slow). Run **~5 rounds** (v0→v5) over C's growing train set; save adapters per version. Optional one **12B hero-final** on the 80GB card.
**Eval — do all of these (this is what judges will probe):**
- **Held-out generalization:** block-rate ↑ across rounds on families never trained on; per-family breakdown (no single family carrying it).
- **Benign FP flat:** false-positive rate on set `D` stays within tolerance every round (the "does it just block everything?" answer).
- **Baselines beaten:** report vs (a) Gemini native defense alone, (b) rules-only, (c) Gemma v0.
- **Ablations:** audio-native vs transcript-only; LoRA rank; train-size curve — so you can defend design choices in Q&A.
- **Leakage/overfit check:** confirm held-out truly unseen (re-run C's firewall against your train set); watch dev vs held-out gap.
- **Promotion:** only promoted versions enter the demo; the v0→v5 **curve renders from `eval_runs`** (held-out block-rate climbing, benign FP flat) — this is the 1:45–2:30 money frame.
- **Latency:** the chosen checkpoint serves within budget on vLLM.

### D5 — Integration dry-run + failure-mode drills (light, but do it)
Build: full team dry-run; rehearse the failure modes from PROJECT.md §9.
**Eval (must pass):**
- Network-drop drill: entire demo runs offline. Native-defense-patch drill: A's fallback L1 still fires. Checkpoint-won't-load drill: pinned versions + cached base weights recover.
- One timed 3:00 run that lands the chart cleanly.
- Each owner's `ASSUMPTIONS.md` is filled and no INV is "at-risk" by go-time.

**Your ASSUMPTIONS.md seeds:** is audio-native fine-tune fast enough or do we ship transcript-fallback? how many rounds did we actually land? E4B vs 12B for the demo number? what's the single weakest link at go-time and who owns it?
