# CLAUDE.md

@AGENTS.md

## Working in this repo with Claude Code

### Read before you start
- Check the current milestone in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) and any related entries in [docs/DECISIONS.md](docs/DECISIONS.md).
- Touching `backend/safety/`, `backend/conversation/`, or `backend/llm/`: read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#pipeline-invariants) first and say which invariants the change touches and how they still hold.

### How to work
- Follow the 8-step workflow in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md#workflow-for-every-feature-prd-153). Propose before implementing anything safety-critical.
- Tests first for the policy engine, the output validator, and fail-closed paths.
- Keep providers in fake mode while developing. Don't enable a live provider until its D-003 answer is recorded.
- If the PRD and the code disagree, stop and ask. Record the outcome in `docs/DECISIONS.md`.

### Subagents
Good uses here:
- Reviewing a diff against the pipeline invariants before it's merged.
- Drafting adversarial test cases. Every proposed case still needs a human-checked expected outcome.
- Searching for content leaking into logs, or any call to `LLMProvider.generate` outside `conversation_manager`.

### Done means
- Tests and lint pass (commands to be added in M1).
- `tests/safety/` passes. If safety code changed, the adversarial suite passes too.
- Docs updated: DECISIONS entry for any choice made, SAFETY_POLICY review status unchanged unless a human reviewed it.

### Things Claude should not do here
- Don't write final wording for sensitive-disclosure templates or mark any template as reviewed.
- Don't move a DECISIONS entry to `Accepted`. Only a named human can.
- Don't add logging that includes transcript, response, or audio content, even temporarily for debugging.
