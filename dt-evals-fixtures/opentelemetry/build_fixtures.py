"""Build fixtures.json from real evaluation datasets (SPEC.md §3.7).

Every fixture's content is drawn from an established eval dataset, never
hand-authored. Genuine multi-turn conversations come from datasets that actually
carry conversations (here: `Anthropic/hh-rlhf` for toxicity); the raw data is
read from the local HuggingFace cache.

This is a dev-time build tool (not part of the runtime app). Its output,
`fixtures.json`, is committed so consumers never need `datasets` or the cache.
Run: `uv run python build_fixtures.py`.
"""

from __future__ import annotations

import glob
import json
import re
from pathlib import Path

from fixtures import DEFAULT_SERVICE_NAME, load_fixtures
from validate import assert_valid

HERE = Path(__file__).resolve().parent
FIXTURES_PATH = HERE / "fixtures.json"

DEFAULT_SYSTEM = "You are a helpful assistant."

# --- hh-rlhf (toxicity, real multi-turn) ------------------------------------

# Curated rows: benign prefix, clean `chosen` (pass), toxic `rejected` (fail).
# Each row yields one matched pass/fail conversation pair.
HHRLHF_TOXICITY_ROWS = [1065]

_TURN_MARKER = re.compile(r"\n\n(Human|Assistant): ")


def parse_transcript(text: str) -> list[tuple[str, str]]:
    """Parse an hh-rlhf transcript into ordered (user, assistant) turn pairs."""
    parts = _TURN_MARKER.split(text)
    it = iter(parts[1:])  # drop the leading empty segment
    roles = [(role, content.strip()) for role, content in zip(it, it)]

    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(roles) - 1:
        if roles[i][0] == "Human" and roles[i + 1][0] == "Assistant":
            pairs.append((roles[i][1], roles[i + 1][1]))
            i += 2
        else:
            i += 1
    return pairs


def _toxicity_case(row: int, expect: str, pairs: list[tuple[str, str]]) -> dict:
    turns = [{"user": u, "response": a} for u, a in pairs]
    # Tag the final turn — the assistant output that carries the verdict.
    turns[-1] = {**turns[-1], "expect": expect, "targets": ["toxicity"]}
    return {
        "name": f"toxicity-hhrlhf-{row}-{expect}",
        "system": DEFAULT_SYSTEM,
        "targets": ["toxicity"],
        "expect": expect,
        "turns": turns,
        "source": {
            "dataset": "Anthropic/hh-rlhf",
            "subset": "harmless-base",
            "row": row,
            "field": "chosen" if expect == "pass" else "rejected",
        },
    }


def build_toxicity_cases(dataset, rows: list[int] = HHRLHF_TOXICITY_ROWS) -> list[dict]:
    """One matched pass (`chosen`) / fail (`rejected`) conversation per row."""
    cases: list[dict] = []
    for row in rows:
        record = dataset[row]
        cases.append(_toxicity_case(row, "pass", parse_transcript(record["chosen"])))
        cases.append(_toxicity_case(row, "fail", parse_transcript(record["rejected"])))
    return cases


def _load_hhrlhf():
    from datasets import Dataset

    matches = glob.glob(
        str(
            Path.home()
            / ".cache/huggingface/datasets/Anthropic___hh-rlhf/**/hh-rlhf-train.arrow"
        ),
        recursive=True,
    )
    if not matches:
        raise FileNotFoundError(
            "Anthropic/hh-rlhf not found in the HF cache. Download it first: "
            "`datasets.load_dataset('Anthropic/hh-rlhf')`."
        )
    return Dataset.from_file(matches[0])


def build_all() -> dict:
    cases = build_toxicity_cases(_load_hhrlhf())
    return {"service_name": DEFAULT_SERVICE_NAME, "cases": cases}


def main() -> None:
    data = build_all()
    FIXTURES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    # Fail loudly if we just wrote something malformed.
    _, cases = load_fixtures(FIXTURES_PATH)
    assert_valid(cases)
    print(f"wrote {len(data['cases'])} cases to {FIXTURES_PATH}")


if __name__ == "__main__":
    main()
