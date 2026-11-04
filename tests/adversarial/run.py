"""Adversarial suite test-run tool.

    uv run python -m tests.adversarial.run --mode fake

fake: runs only the deterministic rules layer (no network). Reports how many block cases the
      rules catch on their own, any rules_should_catch case they miss (a failure), and harmless
      cases the rules over-block.
live: runs the full layered classifier and policy engine against a real provider and reports
      critical failures (a block case allowed). Needs the provider adapters from M2 PR C.

Inputs are synthetic, so failing cases are printed in full to help labelling.
"""

import argparse
import sys
from collections import Counter

from backend.safety.rules import match_input_rules
from tests.adversarial.cases import Case, ExpectedDecision, LabelStatus, load_cases


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=["fake", "live"], default="fake")
    args = parser.parse_args(argv)

    if args.mode == "live":
        print("live mode needs the provider adapters from M2 PR C", file=sys.stderr)
        return 2

    lines, failures = rules_report(load_cases())
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
