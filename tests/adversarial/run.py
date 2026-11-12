"""Adversarial suite test-run tool.

    uv run python -m tests.adversarial.run --mode fake

fake: runs only the deterministic rules layer (no network). Reports how many block cases the
      rules catch on their own, any rules_should_catch case they miss (a failure), and harmless
      cases the rules over-block.
live: runs every case through the layered classifier on Groq, evaluates the policy engine at a
      grid of thresholds, proposes one, then runs the harmless cases through the full pipeline.
      Writes a Markdown report to reports/adversarial/. Synthetic inputs only.

    uv run --env-file .env python -m tests.adversarial.run --mode live

Free-tier daily limits can stop a run partway. To finish it without repeating everything, rerun
only some cases (--cases), or only the reply side at a threshold you choose (--replies-only
--threshold). Subset reports say so in their header.

Inputs are synthetic, so failing cases are printed in full to help labelling.
"""

import argparse
import asyncio
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from backend.llm.groq import (
    GroqClient,
    GroqConfig,
    GroqConfigError,
    GroqJudge,
    GroqLLMProvider,
    GroqModeration,
)
from backend.safety.rules import match_input_rules
from tests.adversarial.analysis import critical_failures
from tests.adversarial.cases import Case, ExpectedDecision, LabelStatus, load_cases
from tests.adversarial.live import Providers, run_live

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports" / "adversarial"


def rules_report(cases: list[Case]) -> tuple[list[str], int]:
    lines: list[str] = []
    missed: list[Case] = []
    over_blocked: list[tuple[Case, list[str]]] = []
    caught_by_category: Counter[str] = Counter()
    blocks_by_category: Counter[str] = Counter()

    for case in cases:
        hits = match_input_rules(case.input)
        if case.expected_decision is ExpectedDecision.BLOCK:
            blocks_by_category[case.expected_category] += 1
            if case.expected_category in hits:
                caught_by_category[case.expected_category] += 1
            elif case.rules_should_catch:
                missed.append(case)
        elif hits:
            over_blocked.append((case, sorted(hits)))

    labels = Counter(c.label_status for c in cases)
    lines.append(
        f"{len(cases)} cases: {labels[LabelStatus.HUMAN_CHECKED]} human_checked, "
        f"{labels[LabelStatus.DRAFT]} draft"
    )
    lines.append("")
    lines.append("Rules layer coverage of block cases (other layers cover the rest):")
    for category in sorted(blocks_by_category):
        lines.append(
            f"  {category:<28} {caught_by_category[category]:>3} / {blocks_by_category[category]}"
        )
    lines.append("")
    lines.append(f"Missed rules_should_catch cases (failures): {len(missed)}")
    for case in missed:
        lines.append(f"  {case.id}: {case.input!r} (expected {case.expected_category})")
    allow_total = sum(1 for c in cases if c.expected_decision is ExpectedDecision.ALLOW)
    lines.append("")
    lines.append(f"Harmless cases over-blocked by rules: {len(over_blocked)} / {allow_total}")
    for case, hits in over_blocked:
        lines.append(f"  {case.id}: {case.input!r} -> {', '.join(hits)}")
    return lines, len(missed)


def select_cases(cases: list[Case], ids: str | None) -> list[Case]:
    """Cases named in a comma-separated id list, in suite order. Unknown ids are an error."""
    if not ids:
        return cases
    wanted = {i.strip() for i in ids.split(",") if i.strip()}
    unknown = wanted - {c.id for c in cases}
    if unknown:
        raise ValueError(f"unknown case ids: {', '.join(sorted(unknown))}")
    return [c for c in cases if c.id in wanted]


async def _live(
    concurrency: int,
    case_ids: str | None = None,
    threshold: float | None = None,
    replies_only: bool = False,
) -> int:
    all_cases = load_cases()
    try:
        cases = select_cases(all_cases, case_ids)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    try:
        config = GroqConfig.from_env()
    except GroqConfigError as exc:
        print(f"live mode needs Groq settings in the environment ({exc})", file=sys.stderr)
        print(
            "run with: uv run --env-file .env python -m tests.adversarial.run --mode live",
            file=sys.stderr,
        )
        return 2

    client = GroqClient(config)
    providers = Providers(
        llm=GroqLLMProvider(client, config),
        judge=GroqJudge(client, config),
        moderation=GroqModeration(client, config),
        description=(
            f"Groq: chat `{config.chat_model}` ({config.chat_reasoning_effort}), "
            f"judge `{config.judge_model}` ({config.judge_reasoning_effort}), "
            f"moderation `{config.moderation_model}` ({config.moderation_reasoning_effort})"
        ),
    )
    try:
        report, inputs, threshold = await run_live(
            cases,
            providers,
            concurrency,
            threshold=threshold,
            replies_only=replies_only,
            subset_of=len(all_cases) if len(cases) < len(all_cases) else None,
        )
    finally:
        await client.aclose()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"live-{datetime.now(UTC):%Y%m%d-%H%M}.md"
    path.write_text(report, encoding="utf-8")
    if inputs:
        print(
            f"threshold {threshold:.2f}; "
            f"critical failures at it: {len(critical_failures(inputs, threshold))}"
        )
    print(f"report: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=["fake", "live"], default="fake")
    parser.add_argument("--concurrency", type=int, default=4, help="live mode: parallel cases")
    parser.add_argument("--cases", help="live mode: comma-separated case ids to run (default: all)")
    parser.add_argument(
        "--threshold",
        type=float,
        help="live mode: confidence threshold for the reply side instead of the proposed one",
    )
    parser.add_argument(
        "--replies-only",
        action="store_true",
        help="live mode: skip the input side; needs --threshold",
    )
    args = parser.parse_args(argv)

    if args.mode != "live" and (args.cases or args.threshold is not None or args.replies_only):
        parser.error("--cases, --threshold and --replies-only need --mode live")
    if args.replies_only and args.threshold is None:
        parser.error("--replies-only needs --threshold")
    if args.threshold is not None and not 0.0 <= args.threshold <= 1.0:
        parser.error("--threshold must be between 0 and 1")

    if args.mode == "live":
        return asyncio.run(_live(args.concurrency, args.cases, args.threshold, args.replies_only))

    lines, failures = rules_report(load_cases())
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
