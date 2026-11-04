# Development

## Milestones

The working build order differs from PRD §14: safety gates exist from the first milestone so there is never an ungated generation path (D-001). Hardware runs in parallel from the start.

| # | Milestone | Done when | PRD phases |
|---|---|---|---|
| M0 | Scaffold, docs, decisions log | Open questions recorded with owners in [DECISIONS.md](DECISIONS.md) | — |
| M1 | Text-only pipeline, every safety stage stubbed to fail closed | Every failure path returns a predefined response; invariant tests in `tests/safety/` pass | 2, 3 |
| M2 | Real classification layers, policy engine, output validation, LLM behind the provider interface; adversarial suite v0 | Adversarial suite runs on every change; no critical failures | 2, 3 |
| M3 | Speech-to-text and text-to-speech; laptop device simulator | A spoken conversation works end to end on a laptop; latency measured | 2, 4 |
| M4 | Raspberry Pi hardware (parallel from M0) | The real device runs the same flow; push-to-talk, mute switch, status LED | 1, 4 |
| M5 | Device credentials and provisioning, minimal parent consent and pairing, data deletion | PRD §12.3 privacy tests pass | 5 |
| M6 | Child-safety, privacy, and security reviews | Approval for a supervised pilot | 5 |

No real child uses the device before D-002 is resolved and M6 is approved.

## Workflow for every feature (PRD §15.3)

1. Read the relevant PRD sections and any related entries in [DECISIONS.md](DECISIONS.md).
2. Identify dependencies.
3. Propose the implementation.
4. Identify safety and privacy implications.
5. Define acceptance tests.
6. Implement the feature.
7. Run tests.
8. Document completion and outstanding limitations.

Safety-critical changes (anything in `backend/safety/`, `backend/conversation/`, templates, or the policy table) need human approval. Agents must not approve them.

## Local development

Not set up yet. Planned for M1:

- Python 3.12, FastAPI, Pytest, Ruff.
- `docker compose up` for PostgreSQL.
- All providers default to fake implementations. Live providers are enabled per provider through environment variables, and only after D-003 is answered for that provider.

## Tests

| Folder | What goes there |
|---|---|
| `tests/unit/` | Per-module tests |
| `tests/integration/` | API and pipeline tests with fake providers |
| `tests/safety/` | Pipeline invariant tests (see [ARCHITECTURE.md](ARCHITECTURE.md)) and fail-closed tests |
| `tests/adversarial/` | Adversarial prompt dataset with expected policy outcomes, and the runner |

Adversarial cases use synthetic input only. Every case needs a human-checked expected outcome.
