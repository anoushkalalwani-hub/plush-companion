# Safety Policy

Status: **skeleton — not reviewed.** Nothing in this file is approved for use with real children.

PRD §15.2: agents must not invent safety policies. This file defines the *structure* that policies will fill in. Concrete wording and category rules require human approval, and sensitive-disclosure templates require review by a qualified child-safety professional (PRD §7.4, D-004).

## Review status

| Item | Status | Reviewer | Date |
|---|---|---|---|
| Category → decision table | Unreviewed | TBD | — |
| Sensitive-disclosure protocol | Unreviewed | TBD (child-safety professional) | — |
| Response templates | Unreviewed | TBD (child-safety professional) | — |
| Generic fallback | Unreviewed | TBD | — |

## Policy version

`policy_version: 0.0.0-unreviewed`

Every policy decision is logged with this version (PRD §7.3, §10 "safety policy version visibility").

## Approved categories (PRD §6.3)

Proceed to generation (`allow`), subject to output validation.

| Category | Allowed behavior |
|---|---|
| General knowledge | Explain ordinary factual topics |
| Education | Age-appropriate explanations |
| Creative writing | Stories and imaginative scenarios |
| Animals and nature | Educational discussion |
| Games | Simple verbal games and riddles |
| Everyday conversation | Friendly, ordinary conversation |
| Emotional support | Basic empathy and encouragement |
| Social situations | General, nonjudgmental guidance |

## Restricted categories (PRD §6.3)

Each needs a defined decision, template, and tests. Decisions below are **TBD — human approval required.**

| Category | Decision | Template ID | Session purge | Tests |
|---|---|---|---|---|
| Medical questions | TBD | TBD | TBD | — |
| Personal information | TBD | TBD | TBD | — |
| Family conflict | TBD | TBD | TBD | — |
| Bullying and mistreatment | TBD | TBD | TBD | — |
| Abuse or unsafe situations | TBD | TBD | TBD | — |
| Dangerous activities | TBD | TBD | TBD | — |
| Sexual content | TBD | TBD | TBD | — |
| Self-harm-related disclosures | TBD | TBD | TBD | — |
| Requests for secrecy | TBD | TBD | TBD | — |
| Requests involving illegal activity | TBD | TBD | TBD | — |
| Ambiguous / unclassifiable | TBD | TBD | TBD | — |

## Sensitive-disclosure protocol (PRD §7.4)

Fixed requirements from the PRD, which every template must satisfy:

- Respond calmly and supportively.
- Never blame or shame the child.
- Never interrogate the child or attempt to investigate.
- Never promise secrecy.
- Encourage speaking with a trusted adult.
- Use expert-reviewed response templates.
- Do not independently contact third parties.
- Do not retain sensitive disclosures as conversational memory.

## Fail-closed fallbacks (PRD §7.6)

Triggers: input classification fails, output moderation fails, LLM timeout, backend connectivity loss, malformed response, validation failure, or a safety decision cannot be made reliably.

Example from the PRD (unreviewed):

> "I'm not sure how to help with that. Maybe we can talk to a grown-up you trust."

The device also needs its own offline fallback, stored on the device, for when the backend is unreachable.

## Output validation checks (PRD §7.5)

- Age appropriateness.
- Restricted content.
- Personal information exposure.
- Dangerous instructions.
- Inappropriate emotional framing.
- Unsupported medical or other high-stakes advice.
- Compliance with the applicable conversational category.
- Persona rules (PRD §6.2): no claims to be human, no claimed physical experiences, no encouraging dependency or secrecy, no discouraging real relationships, no manipulation to keep talking.
- Length: 1–4 short sentences.
