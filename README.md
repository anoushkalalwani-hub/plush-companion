# AI Plush Companion

A stuffed animal with a Raspberry Pi, microphone, and speaker that children aged about 5–10 can talk to. Every message passes through a backend safety pipeline that is independent of the language model, and the system fails closed to predefined responses.

**Status:** M1, text-only backend pipeline with safety stages stubbed to fail closed (every reply is the fallback until M2). Not for use with children (see [D-002](docs/DECISIONS.md#d-002--childrens-privacy-law-and-parental-consent)).

```bash
uv sync && uv run pytest
```

## Docs

| Doc | What it covers |
|---|---|
| [PRD](docs/PRD.md) | Requirements (source of truth) |
| [Decisions](docs/DECISIONS.md) | Open questions and decisions awaiting approval |
| [Architecture](docs/ARCHITECTURE.md) | Components, pipeline invariants, module interfaces |
| [Safety policy](docs/SAFETY_POLICY.md) | Category policies and templates (unreviewed skeleton) |
| [API spec](docs/API_SPEC.md) | Endpoints |
| [Development](docs/DEVELOPMENT.md) | Milestones, workflow, tests |

## Layout

```
device/      Raspberry Pi runtime: audio, controls, connectivity, push-to-talk
backend/     FastAPI backend: auth, sessions, conversation pipeline, safety, providers
parent_app/  Parent interface (later milestone)
tests/       unit, integration, safety invariants, adversarial suite
docs/        PRD and design docs
```

## Next step

M2: real classification layers, output validation, LLM provider, and the adversarial suite. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
