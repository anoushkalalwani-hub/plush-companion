# AGENTS.md

Rules for AI coding agents working on the AI Plush Companion. These come from PRD §15 and are not optional.

## Sources of truth

- [docs/PRD.md](docs/PRD.md): requirements. Treat it as the source of truth.
- [docs/DECISIONS.md](docs/DECISIONS.md): open questions and accepted decisions. Check it before implementing anything it covers.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): pipeline invariants that every change must preserve.
- [docs/SAFETY_POLICY.md](docs/SAFETY_POLICY.md): category policies and templates, with review status.

## General rules

- Do not expand product scope beyond the PRD.
- Do not add autonomous agent functionality, tool calling, or browsing.
- Do not bypass the backend safety pipeline or add unrestricted LLM access.
- Do not store sensitive information for convenience.
- Keep provider-specific code inside provider adapters (`backend/llm/`, `backend/speech/`).
- Write modular, testable code. Every feature ships with tests.
- Record architectural decisions in `docs/DECISIONS.md`.

## Safety rules

- Never assume a system prompt makes output safe.
- Never let generated text reach TTS, the device, or the API response without passing output validation.
- Never stream unvalidated generated text to speech.
- Never treat vector retrieval as a safety boundary.
- Never allow arbitrary tool execution or execute LLM-generated code.
- Never fail open. When a safety service is unavailable, use a predefined fallback.
- Never repair a failed response by asking the LLM to rewrite it without a fresh, independent validation. The default is to discard it.
- Never add persistent child memory without explicit product approval and privacy review.
- Never invent safety policies or template wording. Write placeholders marked unreviewed and add a DECISIONS entry.
- When requirements conflict or are unclear, add an entry to `docs/DECISIONS.md` and ask a human. Do not pick an answer silently.
- Agents must not approve safety-critical changes.

## Pipeline invariants

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#pipeline-invariants). In short: every input is classified; the policy engine is deterministic; only `conversation_manager` calls the LLM and only after `allow`; only validated text is spoken; failures fall back to predefined responses; logs never contain content.

## Privacy rules

- No raw audio on disk, on the device or the backend.
- No transcripts or responses in logs, error messages, or the database by default.
- No provider API keys on the device.
- Use synthetic inputs only in tests and fixtures. Never real children's speech or data.
