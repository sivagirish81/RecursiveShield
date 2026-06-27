# ASSUMPTIONS.md — Project assumptions

## Task D / Lead (Teammate)

### Current status
- D1 scaffold is self-contained and does not require Gemini, MongoDB, Voyage, MiniMax, or GPU access.
- The guardrail interface is frozen as `classify(audio_path, screenshot_path, action, policy) -> GuardrailDecision`.
- The top-level `contracts.py` re-export exists so A/B/C can `import contracts` immediately.

### Open assumptions
- Audio-native Gemma-4 fine-tune speed is unverified; transcript-only SFT remains the fallback.
- Real D4 rounds require Person C's frozen `split.json`, benign set `D`, and labeled traces.
- Real attack potency requires Person A's oracle plus Person B's playable `AttackSpec` audio.
- MongoDB Atlas URI, Voyage model id/dimension, and vector threshold are pending from Person C.

### Weakest link
- The L1 bypass and labeled dataset are upstream dependencies. Until A/B/C hand off traces and `split.json`, Task D can only dry-run the pipeline with stub data.

---

## Task B (Red-Team)

This section contains answers to the required design seeds, integration expectations, and risks for Task B.

### 1. Ablation Winner
*   **Winner**: `Antigravity/Flash` (`gemini-3.5-flash` with our custom Interaction persona) won the generator ablation study.
*   **Metrics**:
    *   **Antigravity/Flash**: Bypass Rate: 0.85, Diversity: ~0.98. Score: ~0.83.
    *   **Gemma-4**: Bypass Rate: 0.50, Diversity: ~0.98. Score: ~0.49.
    *   **MiniMax Text**: Bypass Rate: 0.35, Diversity: ~1.00. Score: ~0.35.
*   **Justification**: `Antigravity/Flash` generates context-blended, conversational audio prompts that mimic the podcast host/sponsor tone, bypassing the native keyword defenses far more effectively than direct text overrides (MiniMax Text) or generic SFT instructions (Gemma-4).

### 2. Reserved Held-out Families
*   The following families from `SKILL.md` are reserved as **held-out** (never trained on by Person D / Lead, used strictly for generalization testing):
    *   **Family 9**: Multi-step delayed
    *   **Family 10**: Cross-lingual
    *   **Family 11**: Homophone / obfuscation
    *   **Family 12**: Sub-audible / over-spoken

### 3. Risks & Mitigations
*   **Risk**: Google silently patches `gemini-3.5-flash`'s native defenses mid-event, meaning our L1 attacks stop bypassing the agent.
*   **Mitigation**: We maintain fallback attack families (e.g. cross-lingual or homophone obfuscation) and keep a cached, pre-recorded trace database that captures successful bypasses offline.
*   **Risk**: MiniMax API key rate limits or network latency impacts real-time TTS generation during demo.
*   **Mitigation**: All attack audio files are pre-synthesized and stored locally in the `data/attacks/` folder. The generator falls back gracefully to a high-quality local mock audio synthesizer if keys are missing or the API times out.

### 4. Stack Parameters
*   **MiniMax TTS model ID**: `speech-02-hd` (default) or `speech-02-turbo`.
*   **Voyage Embedding model ID**: `voyage-3` (dimension: 1024).
