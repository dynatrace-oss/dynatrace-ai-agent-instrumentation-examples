"""Structural validation for fixture cases.

Checks well-formedness, not dataset completeness: names are unique and non-empty,
turns carry content, and — where present — `targets` name real dt-evals
evaluators, `expect` is pass/fail, and evaluators that need extra inputs
(`context` / `reference`) have them. See SPEC.md §3.1/§7.
"""

from fixtures import Case

# dt-evals' 14 judge-based evaluators (README "Built-in Evaluators").
EVALUATORS = frozenset(
    {
        "toxicity",
        "faithfulness",
        "hallucination",
        "relevance",
        "user-frustration",
        "fluency",
        "factual-accuracy",
        "answer-completeness",
        "context-relevance",
        "pii-leakage",
        "prompt-injection",
        "bias",
        "summarization-quality",
        "conciseness",
    }
)

# Evaluators that need a grounding context / source text in the fixture.
NEEDS_CONTEXT = frozenset(
    {"faithfulness", "hallucination", "context-relevance", "summarization-quality"}
)
# Evaluators that need a reference answer.
NEEDS_REFERENCE = frozenset({"factual-accuracy"})

VALID_EXPECT = frozenset({"pass", "fail"})


def validate_cases(cases: list[Case]) -> list[str]:
    """Return a list of human-readable problems; empty means well-formed."""
    errors: list[str] = []
    seen: set[str] = set()

    for case in cases:
        loc = f"case '{case.name}'"

        if not case.name:
            errors.append("a case has an empty name")
        elif case.name in seen:
            errors.append(f"duplicate case name: {case.name}")
        seen.add(case.name)

        if not case.turns:
            errors.append(f"{loc}: has no turns")

        targets = set(case.targets)
        for turn in case.turns:
            targets.update(turn.targets)
        for target in sorted(targets):
            if target not in EVALUATORS:
                errors.append(f"{loc}: unknown evaluator target '{target}'")

        for expect in [case.expect, *(t.expect for t in case.turns)]:
            if expect is not None and expect not in VALID_EXPECT:
                errors.append(f"{loc}: invalid expect '{expect}' (must be pass/fail)")

        missing_context = targets & NEEDS_CONTEXT
        if missing_context and not case.context:
            errors.append(
                f"{loc}: targets {sorted(missing_context)} require a 'context'"
            )
        missing_reference = targets & NEEDS_REFERENCE
        if missing_reference and not case.reference:
            errors.append(
                f"{loc}: targets {sorted(missing_reference)} require a 'reference'"
            )

        for i, turn in enumerate(case.turns):
            if not turn.user or not turn.response:
                errors.append(f"{loc}: turn {i} has an empty user or response")

    return errors


def assert_valid(cases: list[Case]) -> None:
    """Raise ValueError listing every problem if the cases are not well-formed."""
    errors = validate_cases(cases)
    if errors:
        raise ValueError(
            "fixtures are not well-formed:\n" + "\n".join(f"  - {e}" for e in errors)
        )
