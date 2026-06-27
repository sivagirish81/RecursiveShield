# TASK C — Data Pipeline + Shared MongoDB + Voyage
**Owner:** Person C · **Branch:** `feat/data-memory` · **Owns:** INV-3 + Push Gate "Eval harness data" + **the shared Atlas cluster**
**Read first:** `PROJECT.md`. You own the **data-quality gate** between red-team and trainer, **and** you create + share the MongoDB Atlas cluster everyone uses. The single thing that can quietly kill our credibility is **train/held-out leakage** — your split is the firewall. Treat "is this attack actually hard?" as an empirical question you test, not assume.

## STACK LOCK (identical for all 4 — verify in Task C1, do not drift)
- Python **3.11**. **MongoDB Atlas + Atlas Vector Search**; `pymongo`. DB name **`agentimmune`** (one cluster, you own it).
- Embeddings: **Voyage** via `voyageai` SDK — confirm current model (e.g. `voyage-3.5`) at the MongoDB table; pin one model id for all of us.
- Agent under test for difficulty labeling: `gemini-3.5-flash` (native defense ON) via Person A's oracle.
- Gemini SDK `google-genai >= 2.3.0`. Guardrail base `unsloth/gemma-4-E4B-it`.
- **Sponsors you touch:** MongoDB (Atlas + Vector Search) + Voyage (embeddings). Stage: the data/memory layer.

## Interface contracts (import from Lead)
- You **consume** `AttackSpec` + audio (from B), `OracleLabel` (from A's oracle), benign runs (real Fed audio).
- You **produce** the labeled, deduped, **split** dataset (`train/dev/held_out`), the benign set `D`, and a **retrieval API** ("seen a similar attack?"). You write `attacks`, `attack_embeddings`, `traces`, `eval_runs` collections.

---

### C1 — Create + share the Atlas cluster, verify Stack Lock
Build: provision a free/shared **Atlas cluster**, DB `agentimmune`, collections `traces / attacks / attack_embeddings / model_versions / eval_runs`. Create the **Vector Search index** on `attack_embeddings`. Share the connection string (read/write) with the team via a secret, not the repo.
**Eval (must pass):**
- A/B/Lead can each connect and write a test doc (round-trip from 3 machines).
- Voyage embed call returns the expected dimension; the vector index returns nearest-neighbors on a 5-doc smoke test.
- Pin and broadcast the exact **Voyage model id** + vector dimension to all 4 `ASSUMPTIONS.md` files.

### C2 — Ingestion + schema validation
Build: ingest `AttackSpec`s (B) and `Trace`s (A); validate against Lead's contracts on write (reject malformed).
**Eval (must pass):**
- Feed 20 specs incl. 3 deliberately malformed → 17 accepted, 3 rejected with clear errors (no silent corruption).
- Every stored attack has a resolvable `audio_path` and a `source_transcript_id`.
- Idempotent ingest: re-running doesn't duplicate (`attack_id` is the key).

### C3 — Oracle labeling + difficulty bucketing (does it *really* break Gemini?)
Build: for each attack, run it through Person A's agent+oracle, store the `OracleLabel`, and bucket **easy** (native defense caught) vs **hard** (bypassed). Same pipeline labels the benign set.
**Eval (must pass):**
- Auto-labels match a **hand-checked gold set of ≥30** at **≥95%** agreement.
- The "hard" bucket is genuinely hard: spot-check that those L1s actually bypass native defense (re-run 10) — if a labeled-hard attack is now caught, re-bucket it. This is the empirical "really breaks Gemini" test the lead asked for.
- Benign set `D` is built from **real Fed-audio compliant trades**, labeled `safe`, ≥15 examples.

### C4 — Voyage embeddings + novelty / dedup
Build: embed every attack (payload + transcript context) with Voyage; store vectors; flag near-duplicates via vector search.
**Eval (must pass):**
- Duplicate detection catches a known planted pair (cosine > τ) and does **not** flag two genuinely different families.
- Report the intra-family vs inter-family distance gap; confirm families are separable (supports INV-2).
- Embedding throughput handles the full set within the build window (batch the calls).

### C5 — Deterministic split + leakage firewall (INV-3 core)
Build: deterministic `train / dev / held_out` split by **hash(family, seed)** so **whole families** B reserved are held-out and never train. Build benign `D`. Emit a frozen `split.json`.
**Eval (must pass):**
- **Leakage assertion test:** no `attack_id`, no `(family,seed)`, and no near-duplicate (Voyage cosine > τ) appears in both train and held-out. Automated, must return **zero** — this is the firewall.
- Held-out contains ≥2 **families** absent from train (so "blocked held-out" = real generalization, not memorization).
- Re-running the split is byte-identical (determinism check).

### C6 — Retrieval API + eval_runs store
Build: `similar_attacks(query) → top-k` for the runtime guardrail/memory, and a writer for Lead's per-round `eval_runs`.
**Eval (must pass):**
- Given a held-out attack, retrieval surfaces a same-family train attack above an unrelated one (precision@k sane).
- Lead can write/read a round's metrics (`held_out_block_rate`, `benign_fp_rate`, `per_family`) and you can render the demo curve from `eval_runs` alone.
- API responds within the demo latency budget (cache hot queries).

**ASSUMPTIONS.md seeds:** Voyage model id + dimension + τ threshold? which families are held-out (must match B)? biggest leakage risk + how your test catches it? cluster connection-sharing method?
