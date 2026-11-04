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

## Milestone status

**M2 (in progress).** M2 ships as four PRs:
- **A (this change):** judge and moderation interfaces, three-layer input classifier (D-005), three-part output validator (D-006), deterministic rules. Not wired into the app yet: it needs provider adapters (PR C), so the app still uses the M1 stand-ins.
- **B:** adversarial case format (`tests/adversarial/cases.csv`), 121 draft cases, test-run tool. Built on top of A.
- **C:** Groq adapters (D-016) for reply generation, the judge and moderation, with simulated HTTP tests. The API app still refuses live mode.
- **D:** first live test run on synthetic input, threshold proposal.

**M1 (text-only pipeline): merged.** What ships by default:

| Stage | M1 default | Effect |
|---|---|---|
| Input classifier | `StubClassifier`, always unavailable | Every message falls back |
| Policy engine | Real and deterministic; confidence threshold unset | Blocks everything until a threshold is set from evaluation (D-005) |
| LLM | `FakeLLMProvider` only; live mode refuses to start | No network calls |
| Output validator | `StubValidator`, rejects everything | Generated text is never returned |
| Restricted categories | Blocked with the generic fallback | Dedicated templates wait for D-004 |

So the API always answers with the generic fallback until M2. Tests swap in allowing test doubles (`tests/fakes.py`) to exercise the full path. Those doubles live only under `tests/`.

Known M1 limitations: no rate limiting (D-013), one shared development token instead of per-device credentials (D-010), no adversarial suite yet (M2), no PostgreSQL usage yet.

## Local development

Requires [uv](https://docs.astral.sh/uv/). It installs Python 3.12 and the dependencies.

```bash
uv sync
```

```bash
uv run pytest
```

```bash
uv run ruff check . && uv run ruff format --check .
```

Run the API locally (every reply will be the fallback):

```bash
DEV_DEVICE_TOKEN=dev uv run uvicorn backend.main:create_app --factory --reload
```

`docker compose up` starts PostgreSQL, which is not used until M5.

All providers default to fake implementations. Live providers are enabled per provider through environment variables, and only after D-003 is answered for that provider.

## Tests

| Folder | What goes there |
|---|---|
| `tests/unit/` | Per-module tests |
| `tests/integration/` | API and pipeline tests with fake providers |
| `tests/safety/` | Pipeline invariant tests (see [ARCHITECTURE.md](ARCHITECTURE.md)), fail-closed tests, no-content-in-logs tests, session context rules |
| `tests/adversarial/` | Adversarial prompt dataset with expected policy outcomes, and the runner |

Adversarial cases use synthetic input only. Every case needs a human-checked expected outcome.

### Adversarial suite

Cases live in [tests/adversarial/cases.csv](../tests/adversarial/cases.csv), one row per case, editable in a spreadsheet. Agents draft cases with `label_status = draft`; **Anoushka Lalwani** confirms each expected outcome and changes it to `human_checked`. Only `human_checked` cases count toward the PRD §12.2 release gate. The loader rejects inconsistent rows (for example a restricted category marked `allow`).

Run the report:

```bash
uv run python -m tests.adversarial.run --mode fake
```

Fake mode checks only the deterministic rules layer: which block cases it catches alone, any `rules_should_catch` case it misses (a failure), and harmless cases it over-blocks. `pytest` runs the same checks, plus a "fooled judge" test: every `rules_should_catch` case must still be blocked when moderation sees nothing and the LLM judge calls it harmless. Live mode (full classifier against a real provider) arrives with PR C.
