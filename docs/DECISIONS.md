# Decisions and Open Questions

PRD §15.2: when requirements conflict or are ambiguous, document the conflict and request human approval. This file is where that happens.

**How to use this file**

- Every entry has an ID, a status, and an owner.
- Statuses: `Open` (needs an answer), `Proposed` (has a recommendation, awaiting human approval), `Accepted`, `Rejected`, `Superseded`.
- Agents may add entries and write recommendations. Only a named human may move an entry to `Accepted`. Safety-critical entries (marked **[safety]**) also need sign-off from the child-safety reviewer.
- When an entry is accepted, add the date and who approved it. Don't edit the PRD to match; reference the decision ID instead.

Owners are `TBD` until someone is assigned.

---

## Summary

| ID | Topic | Status | Owner | Blocks |
|---|---|---|---|---|
| D-001 | Build order: safety gates from milestone 1 | Proposed | TBD | M1 |
| D-002 | Children's privacy law (COPPA / GDPR-K) and parental consent | Open | TBD | Any use by a real child |
| D-003 | Provider terms and data retention for child-directed use | Open | TBD | M2 (live providers) |
| D-004 | Sensitive-disclosure response templates and reviewer **[safety]** | Open | TBD | M2 restricted categories |
| D-005 | Input classification layers and precedence **[safety]** | Proposed | TBD | M2 |
| D-006 | Meaning of "independent" output validation **[safety]** | Proposed | TBD | M2 |
| D-007 | Latency vs. no streaming of unvalidated text | Proposed | TBD | M3 |
| D-008 | Session context lifetime and purge on sensitive disclosure | Proposed | TBD | M1 |
| D-009 | Safety event log schema | Proposed | TBD | M1 |
| D-010 | Device provisioning before the parent app exists | Proposed | TBD | M5 |
| D-011 | Wake mechanism and mute switch implementation | Proposed | TBD | M4 |
| D-012 | Project location (own folder and git repo) | Done | Project owner | — |
| D-013 | Rate limiting deferred past M1 | Proposed | TBD | M5 |
| D-014 | Classifier category set | Proposed | TBD | M2 |

---

## D-001 — Build order: safety gates from milestone 1

- **Status:** Proposed
- **PRD refs:** §14, §7.6, §15.2
- **Conflict:** The PRD roadmap builds an end-to-end generation pipeline in Phase 2 and adds safety enforcement in Phase 3. That leaves a period where an ungated generation path exists, which conflicts with §15.2 ("never allow generated content to bypass output validation").
- **Recommendation:** Merge Phases 2 and 3 in practice. Milestone 1 builds the full pipeline shape (input classification → policy engine → LLM → output validation → fallback) with every safety stage stubbed to fail closed. Real stages replace stubs one at a time. The conversation orchestrator is the only code that may call `LLMProvider.generate`, and only after a policy decision of `allow`. See [DEVELOPMENT.md](DEVELOPMENT.md) for the milestone plan.
- **Decision:** —

## D-002 — Children's privacy law and parental consent

- **Status:** Open
- **PRD refs:** §9, §10, §14 Phase 5
- **Gap:** The PRD does not name the legal frameworks that apply to collecting data from children under 13 (for example COPPA in the US, GDPR Article 8 / the UK Age Appropriate Design Code in Europe). These typically require verifiable parental consent *before* any collection, including voice. The PRD defers parent accounts and pairing to Phase 5.
- **Questions for a human:**
  1. Which jurisdictions will the pilot run in?
  2. Who provides legal/privacy review, and when?
  3. What is the minimum consent flow required before the first supervised session with a real child?
- **Recommendation:** Treat a minimal consent and pairing step as a prerequisite for *any* session with a real child, even a supervised pilot. Until then, development and testing use adult testers and synthetic inputs only.
- **Decision:** —

## D-003 — Provider terms and data retention

- **Status:** Open
- **PRD refs:** §5.1, §6.1, §9
- **Gap:** Audio and transcripts sent to hosted speech-to-text, LLM, moderation, and text-to-speech providers are data collection, even if our backend stores nothing.
- **Questions for a human:**
  1. Do the chosen providers' terms permit products directed at children under 13?
  2. Can zero or minimal data retention be enabled on each provider account? Is it contractually guaranteed?
  3. Where is data processed geographically?
- **Recommendation:** Record the answer per provider in this entry before switching any provider from fake to live mode with real (non-synthetic) input.
- **Decision:** —

## D-004 — Sensitive-disclosure response templates **[safety]**

- **Status:** Open
- **PRD refs:** §7.4, §7.6, §15.2 ("never invent safety policies")
- **Gap:** The PRD requires expert-reviewed templates for sensitive disclosures and context-specific fallbacks, but provides only one generic example.
- **Recommendation:** Agents write placeholder templates only, each marked `REVIEW_STATUS = "unreviewed"` in code and listed in [SAFETY_POLICY.md](SAFETY_POLICY.md). Unreviewed templates must not be used with real children. A named child-safety professional owns the final wording.
- **Questions for a human:** Who is the reviewer? What is the review turnaround?
- **Decision:** —

## D-005 — Input classification layers and precedence **[safety]**

- **Status:** Proposed
- **PRD refs:** §7.2, §7.3
- **Gap:** §7.3 says the policy engine must not rely *exclusively* on LLM classification, but does not say what else it uses or how disagreements are resolved.
- **Recommendation:** Three layers, evaluated independently:
  1. **Deterministic rules:** keyword/phrase lists per restricted category, and pattern detectors for personal information (names with addresses, phone numbers, school names, etc.).
  2. **Moderation API:** provider moderation endpoint.
  3. **LLM classifier:** structured output per §7.2, schema-validated.

  The policy engine takes the **most restrictive** outcome across layers. Any layer failing, timing out, or returning malformed output counts as "cannot decide" and triggers fallback. Confidence thresholds are set from adversarial-suite results, not defaults.
- **Decision:** —

## D-006 — Meaning of "independent" output validation **[safety]**

- **Status:** Proposed
- **PRD refs:** §7.1, §7.5
- **Recommendation:** Output validation is independent when it does not share a prompt, conversation context, or model call with generation. Validation consists of: deterministic checks (length, personal information patterns, banned phrases such as claims to be human or secrecy language), the moderation API, and a separate LLM validator call with its own prompt that sees only the candidate response and the policy category. A failed response is discarded, never repaired.
- **Open sub-question:** Should the LLM validator use a different model or provider from the generator?
- **Decision:** —

## D-007 — Latency vs. no streaming

- **Status:** Proposed
- **PRD refs:** §7.5, §13, §15.2 ("never stream unvalidated generated text to speech")
- **Recommendation:** Validate the complete response before text-to-speech starts. Rely on the 1–4 sentence limit to keep generation and validation short. Run independent validation checks in parallel. Measure end-to-end latency at M3 and set a target then. Text-to-speech audio for approved text may be streamed to the device, since the text has already passed validation.
- **Decision:** —

## D-008 — Session context lifetime

- **Status:** Proposed
- **PRD refs:** §7.4, §8.1
- **Recommendation:** Session context lives in memory only (never the database), keeps the last N turns (N to be set, suggest 6), and expires after an idle timeout (suggest 5 minutes) or on `DELETE /sessions/{id}`. When input is classified as a sensitive disclosure, the session context is purged immediately and the next turn starts fresh.
- **Decision:** —

## D-009 — Safety event log schema

- **Status:** Proposed
- **PRD refs:** §7.3, §9
- **Recommendation:** Log only: timestamp, device ID, session ID, pipeline stage, category label, risk level, policy decision, failure reason code, policy version, latency. Never log transcript text, response text, or audio. For adversarial-suite runs (synthetic input only), full text may be written to test reports, never to production logs.
- **Decision:** —

## D-010 — Device provisioning before the parent app

- **Status:** Proposed
- **PRD refs:** §9, §10, §11
- **Recommendation:** A command-line provisioning script, run by an operator, issues a unique credential per device and records it (hashed) in the database. Credentials are revocable individually. The Pi stores only its own device credential, never provider API keys.
- **Decision:** —

## D-011 — Wake mechanism and mute switch

- **Status:** Proposed
- **PRD refs:** §4.2, §4.3
- **Recommendation:** Push-to-talk for the MVP (no wake word, no always-on listening). The mute switch physically cuts power or signal to the microphone rather than relying on software. An LED indicates when the mic is active.
- **Decision:** —

## D-012 — Project location

- **Status:** Done
- **Context:** The project was first scaffolded as `plush-companion/` inside the `claude-test` workspace. On 2026-11-04, at the project owner's request, it was moved to its own folder at `/Users/anoushka/plush-companion`. It is not yet a git repository.
- **Recommendation:** Initialize it as its own git repository before the first real code lands, so history, CI, and access control are separate from unrelated work.
- **Decision:** Own folder: done 2026-11-04 (requested by the project owner). Git repository: initialized 2026-11-04 at the project owner's request, remote `https://github.com/anoushkalalwani-hub/plush-companion`.

## D-013 — Rate limiting deferred past M1

- **Status:** Proposed
- **PRD refs:** §11 ("all endpoints must implement ... appropriate rate limiting")
- **Conflict:** M1 implements the session endpoints without rate limiting. Meaningful limits are per device, and per-device identity does not exist until real credentials land (D-010).
- **Recommendation:** Accept the gap for M1 and M2 (fake providers, development token, no real users). Add per-device rate limiting together with device credentials in M5, before any live provider is reachable from a real device.
- **Decision:** —

## D-014 — Classifier category set

- **Status:** Proposed
- **PRD refs:** §6.3, §7.2
- **Gap:** §7.2 lists classifier intents (ordinary, educational, creative, personal information, sensitive disclosure, dangerous, medical, inappropriate, ambiguous), while §6.3 lists conversation categories. They overlap but don't match one to one.
- **M1 choice:** `Category` in `backend/safety/classifier.py` uses the §6.3 approved and restricted categories plus `unclassifiable`. §7.2's "sensitive disclosure" is carried by `requires_special_handling`, which always blocks and purges session context.
- **Recommendation:** Confirm or revise this mapping before the M2 classifier is built, since the adversarial suite's expected outcomes depend on it.
- **Decision:** —
