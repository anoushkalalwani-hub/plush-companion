# Architecture

Status: initial draft (M0). Describes the intended design; nothing below is implemented yet.

Source of truth: [PRD.md](PRD.md) §3, §5, §7. Open questions: [DECISIONS.md](DECISIONS.md).

## Components

```
┌──────────────┐  HTTPS   ┌──────────────────────────── Backend (FastAPI) ────────────────────────────┐
│ Device (Pi)  │ ───────▶ │ auth → session → speech_service (STT)                                     │
│ push-to-talk │          │              → conversation_manager (orchestrator)                        │
│ mic / speaker│ ◀─────── │                  1. input classification (rules + moderation + LLM)       │
│ mute switch  │  audio   │                  2. policy engine (deterministic)                         │
│ status LED   │          │                  3. LLMProvider.generate   (only if policy = allow)       │
└──────────────┘          │                  4. output validation      (independent of step 3)        │
                          │                  5. tts_service            (only validated text)          │
                          │              → audit_logger (metadata only)                               │
                          └───────────────────────────────────────────────────────────────────────────┘
```

The device never talks to an AI provider directly and never holds provider keys (PRD §4.1, §9).

## Pipeline invariants

These hold for every code path. Tests in `tests/safety/` enforce them.

1. **Every input is classified.** No message reaches the policy engine without a classification result, and a missing, failed, timed-out, or malformed classification is treated as "cannot decide."
2. **The policy engine is deterministic.** Given the same classification results and policy version, it returns the same decision. It never calls an LLM.
3. **Generation only after `allow`.** `conversation_manager` is the only module that calls `LLMProvider.generate`, and only after the policy engine returns `allow`.
4. **Nothing unvalidated is spoken.** Only text that has passed output validation is sent to TTS. No partial or streamed generated text reaches TTS.
5. **Failed responses are discarded, not repaired.** If validation fails, the response is dropped and a predefined fallback is used.
6. **Fail closed.** Any exception, timeout, or unavailable service in steps 1–5 results in a predefined fallback response, never a generated one.
7. **No content in logs.** Logs carry event metadata only (see D-009).

## Policy decisions

The policy engine returns one of:

| Decision | Meaning |
|---|---|
| `allow` | Proceed to generation within the approved category (PRD §6.3). |
| `template` | Skip generation; respond with a predefined template for the restricted category. |
| `block` | Skip generation; respond with a generic safe fallback. |

Restricted categories (PRD §6.3) map to `template` or `block` according to [SAFETY_POLICY.md](SAFETY_POLICY.md).

## Module interfaces (planned)

Each module gets a documented interface and its own tests (PRD §5.2). Provider-specific code lives only in provider adapters.

| Module | Folder | Interface sketch |
|---|---|---|
| `llm_provider` | `backend/llm/` | `LLMProvider.generate(messages, constraints) -> GenerationResult` |
| `intent_classifier` | `backend/safety/classifier.py` | `classify(text) -> ClassificationResult` |
| `safety_engine` | `backend/safety/policy_engine.py` | `decide(classifications, policy_version) -> PolicyDecision` |
| `response_validator` | `backend/safety/validator.py` | `validate(text, category) -> ValidationResult` |
| templates | `backend/safety/templates.py` | Predefined responses with review status |
| `conversation_manager` | `backend/conversation/` | `handle_message(session, text) -> ApprovedResponse` |
| `session_manager` | `backend/sessions/` | In-memory session context with TTL (D-008) |
| `speech_service` / `tts_service` | `backend/speech/` | `transcribe(audio) -> text`, `synthesize(text) -> audio` |
| `device_manager` / `authentication` | `backend/devices/`, `backend/auth/` | Device registration, credential checks, revocation |
| `memory_manager` | `backend/memory/` | Disabled for MVP (PRD §8.1) |
| `audit_logger` | `backend/api/` or shared | Metadata-only event logging |

Every external provider has a fake implementation used by default in tests and local development.

## Data storage

| Data | Stored? |
|---|---|
| Raw audio | No (processed in memory only) |
| Transcripts / responses | No, by default |
| Session context | In memory only, with TTL (D-008) |
| Device records and hashed credentials | Yes, PostgreSQL |
| Safety event metadata | Yes, no content (D-009) |
| Parent settings | Yes (later milestones) |
