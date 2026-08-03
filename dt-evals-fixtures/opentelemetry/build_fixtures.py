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

# A plausible production model name + token usage so spans carry
# gen_ai.request.model and gen_ai.usage.* instead of "unknown"/empty. The source
# datasets have no token counts, so usage is estimated deterministically from the
# content (~4 chars/token) — same content always yields the same numbers.
DEFAULT_MODEL = "gpt-4o-mini"


def _estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def _attach_model_usage(case: dict) -> dict:
    """Attach a default model name and content-derived token usage if the
    builder did not set them."""
    case.setdefault("model", DEFAULT_MODEL)
    prompt = case.get("system", "") + " " + " ".join(t["user"] for t in case["turns"])
    if case.get("context"):
        prompt += " " + case["context"]
    completion = " ".join(t["response"] for t in case["turns"])
    case.setdefault(
        "usage",
        {
            "input_tokens": _estimate_tokens(prompt),
            "output_tokens": _estimate_tokens(completion),
        },
    )
    return case

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


# --- soda_eval (fluency, real multi-turn) -----------------------------------

# Curated rows: score-5 no-issue dialogues (fluent, pass) and issue-flagged
# dialogues with coherence/repetition problems (fail). Chosen with an even
# utterance count so the evaluated `response` is the final assistant turn.
SODA_FLUENCY_ROWS = {"pass": [16], "fail": [222]}


def _strip_speaker(line: str) -> str:
    """'Ashli: Don't be sorry.' -> 'Don't be sorry.' (drop the speaker label)."""
    return line.split(": ", 1)[1].strip() if ": " in line else line.strip()


def _soda_utterances(record: dict) -> list[str]:
    """Full utterance sequence: dialog history + the evaluated response."""
    lines = [l for l in record["dialog_history"].split("\n") if l.strip()]
    lines.append(record["response"])
    utterances = [_strip_speaker(l) for l in lines]
    # Keep the evaluated response as the final assistant turn: an even count maps
    # cleanly to (user, assistant) pairs, so drop the oldest line if it is odd.
    if len(utterances) % 2 == 1:
        utterances = utterances[1:]
    return utterances


def _fluency_case(row: int, expect: str, utterances: list[str]) -> dict:
    turns = [
        {"user": utterances[i], "response": utterances[i + 1]}
        for i in range(0, len(utterances), 2)
    ]
    turns[-1] = {**turns[-1], "expect": expect, "targets": ["fluency"]}
    return {
        "name": f"fluency-soda-{row}-{expect}",
        "system": DEFAULT_SYSTEM,
        "targets": ["fluency"],
        "expect": expect,
        "turns": turns,
        "source": {"dataset": "Johndfm/soda_eval", "row": row, "field": "response"},
    }


def build_fluency_cases(dataset, rows: dict[str, list[int]] = SODA_FLUENCY_ROWS) -> list[dict]:
    """Fluent (pass) and issue-flagged (fail) conversations from soda_eval."""
    cases: list[dict] = []
    for expect, indices in rows.items():
        for row in indices:
            cases.append(_fluency_case(row, expect, _soda_utterances(dataset[row])))
    return cases


# --- single-turn evaluators (real rows wrapped as 1-turn conversations) -----
#
# Each real (question, answer) row becomes a one-turn conversation. Genuine
# multi-turn only comes from datasets that carry conversations (toxicity,
# fluency); here the source is single-turn, so the case is single-turn — the
# content is still 100% real (SPEC.md §3.3/§3.7).


def _single_turn_case(
    name, target, expect, user, response, *, context=None, reference=None, source=None
) -> dict:
    turn = {"user": user, "response": response, "expect": expect, "targets": [target]}
    case = {
        "name": name,
        "system": DEFAULT_SYSTEM,
        "targets": [target],
        "expect": expect,
        "turns": [turn],
    }
    if context is not None:
        case["context"] = context
    if reference is not None:
        case["reference"] = reference
    if source is not None:
        case["source"] = source
    return case


# Fixed scaffolds for the non-evaluated half of a turn, used only when the
# source dataset provides just one side (SPEC.md §3.7). The evaluated half is
# always real; scaffolded cases record "scaffold" in their source.
_SCAFFOLD_ANSWER = "Sure, I can help with that. Here is the information you requested."
_SCAFFOLD_FRUSTRATION_ANSWER = (
    "I understand this is frustrating. Let me help you sort it out right away."
)
_SCAFFOLD_PII_USER = (
    "Can you share the full customer record you have on file for this account?"
)
_SCAFFOLD_SUMMARIZE_USER = "Summarize the following article."
_SCAFFOLD_BIAS_USER = "Share your honest opinion about the following statement."


def _find_index(dataset, predicate, limit: int = 60000) -> int:
    """First row index matching `predicate` (deterministic, reproducible)."""
    for i in range(min(len(dataset), limit)):
        if predicate(dataset[i]):
            return i
    raise LookupError("no row matched the predicate")


def build_faithfulness_cases(dataset, row: int = 0) -> list[dict]:
    """FaithEval-counterfactual: answer supported by the (counterfactual) context
    is faithful (pass); another choice is not grounded in it (fail)."""
    rec = dataset[row]
    choices = rec["choices"]
    if isinstance(choices, str):
        choices = json.loads(choices)
    labels, texts = choices["label"], choices["text"]
    key = rec["answerKey"]
    faithful = texts[labels.index(key)]
    unfaithful = next(t for l, t in zip(labels, texts) if l != key)
    src = {
        "dataset": "Salesforce/FaithEval-counterfactual-v1.0",
        "row": row,
        "field": "choices",
    }
    return [
        _single_turn_case(
            f"faithfulness-faitheval-{row}-pass", "faithfulness", "pass",
            rec["question"], faithful, context=rec["context"], source=src,
        ),
        _single_turn_case(
            f"faithfulness-faitheval-{row}-fail", "faithfulness", "fail",
            rec["question"], unfaithful, context=rec["context"], source=src,
        ),
    ]


def build_hallucination_cases(dataset) -> list[dict]:
    """FinQA: is_correct==1 is grounded (pass), ==0 is hallucinated (fail)."""

    def case(idx: int, expect: str) -> dict:
        r = dataset[idx]
        return _single_turn_case(
            f"hallucination-finqa-{idx}-{expect}", "hallucination", expect,
            r["query"], str(r["llm_response"]), context=r["context"],
            source={
                "dataset": "Cleanlab/FinQA-hallucination-detection",
                "row": idx,
                "field": "llm_response",
            },
        )

    return [
        case(_find_index(dataset, lambda r: r["is_correct"] == 1), "pass"),
        case(_find_index(dataset, lambda r: r["is_correct"] == 0), "fail"),
    ]


def build_relevance_cases(dataset) -> list[dict]:
    """HelpSteer2: high helpfulness is relevant (pass), low is not (fail)."""

    def case(idx: int, expect: str) -> dict:
        r = dataset[idx]
        return _single_turn_case(
            f"relevance-helpsteer2-{idx}-{expect}", "relevance", expect,
            r["prompt"], r["response"],
            source={"dataset": "nvidia/HelpSteer2", "row": idx, "field": "response"},
        )

    return [
        case(_find_index(dataset, lambda r: r["helpfulness"] >= 4), "pass"),
        case(_find_index(dataset, lambda r: r["helpfulness"] <= 1), "fail"),
    ]


def build_factual_accuracy_cases(dataset, row: int = 0) -> list[dict]:
    """TruthfulQA: the best answer is accurate (pass); an incorrect answer is
    not (fail). The best answer is the reference."""
    r = dataset[row]
    best = r["Best Answer"]
    incorrect = next(
        s.strip() for s in r["Incorrect Answers"].split(";") if s.strip()
    )
    src = {"dataset": "domenicrosati/TruthfulQA", "row": row}
    return [
        _single_turn_case(
            f"factual-accuracy-truthfulqa-{row}-pass", "factual-accuracy", "pass",
            r["Question"], best, reference=best, source={**src, "field": "Best Answer"},
        ),
        _single_turn_case(
            f"factual-accuracy-truthfulqa-{row}-fail", "factual-accuracy", "fail",
            r["Question"], incorrect, reference=best,
            source={**src, "field": "Incorrect Answers"},
        ),
    ]


def build_answer_completeness_cases(dataset) -> list[dict]:
    """Magneto: a COMPLETE answer passes, an INCOMPLETE one fails."""

    def case(idx: int, expect: str) -> dict:
        r = dataset[idx]
        return _single_turn_case(
            f"answer-completeness-magneto-{idx}-{expect}", "answer-completeness", expect,
            r["question"], r["answer"],
            source={
                "dataset": "Magneto/qa-dataset-llm-judge-flattened",
                "row": idx,
                "field": "evaluation_completeness",
            },
        )

    return [
        case(_find_index(dataset, lambda r: r["evaluation_completeness"] == "COMPLETE"), "pass"),
        case(_find_index(dataset, lambda r: r["evaluation_completeness"] == "INCOMPLETE"), "fail"),
    ]


def build_pii_leakage_cases(dataset, row: int = 0) -> list[dict]:
    """Nemotron-PII: the document `text` leaks PII (fail); the generic
    `document_description` carries none (pass). The user prompt is scaffolded."""
    rec = dataset[row]

    def src(field: str) -> dict:
        return {"dataset": "nvidia/Nemotron-PII", "row": row, "field": field, "scaffold": "user"}

    return [
        _single_turn_case(
            f"pii-leakage-nemotron-{row}-pass", "pii-leakage", "pass",
            _SCAFFOLD_PII_USER, rec["document_description"],
            source=src("document_description"),
        ),
        _single_turn_case(
            f"pii-leakage-nemotron-{row}-fail", "pii-leakage", "fail",
            _SCAFFOLD_PII_USER, rec["text"], source=src("text"),
        ),
    ]


def build_summarization_cases(dataset, row: int = 0) -> list[dict]:
    """SummEval: the most vs least consistent machine summary of one article
    (context). The summarize instruction is scaffolded."""
    rec = dataset[row]
    consistency = rec["consistency"]
    summaries = rec["machine_summaries"]
    hi = max(range(len(consistency)), key=lambda i: consistency[i])
    lo = min(range(len(consistency)), key=lambda i: consistency[i])

    def src(i: int) -> dict:
        return {
            "dataset": "mteb/summeval",
            "row": row,
            "summary_index": i,
            "field": "machine_summaries",
            "scaffold": "user",
        }

    return [
        _single_turn_case(
            f"summarization-quality-summeval-{row}-pass", "summarization-quality", "pass",
            _SCAFFOLD_SUMMARIZE_USER, summaries[hi], context=rec["text"], source=src(hi),
        ),
        _single_turn_case(
            f"summarization-quality-summeval-{row}-fail", "summarization-quality", "fail",
            _SCAFFOLD_SUMMARIZE_USER, summaries[lo], context=rec["text"], source=src(lo),
        ),
    ]


def build_prompt_injection_cases(dataset) -> list[dict]:
    """neuralchemy: benign input passes, injection input fails. The evaluator
    scores the user input; the assistant response is scaffolded."""

    def case(idx: int, expect: str) -> dict:
        r = dataset[idx]
        return _single_turn_case(
            f"prompt-injection-neuralchemy-{idx}-{expect}", "prompt-injection", expect,
            r["text"], _SCAFFOLD_ANSWER,
            source={
                "dataset": "neuralchemy/Prompt-injection-dataset",
                "row": idx,
                "field": "text",
                "scaffold": "response",
            },
        )

    return [
        case(_find_index(dataset, lambda r: r["label"] == 0), "pass"),
        case(_find_index(dataset, lambda r: r["label"] == 1), "fail"),
    ]


def build_context_relevance_cases(dataset, row: int = 0) -> list[dict]:
    """gooaq: a retrieved doc labelled relevant to the query (pass) vs one
    labelled irrelevant (fail). The doc is the context; response is scaffolded."""
    rec = dataset[row]
    texts, labels = rec["texts"], rec["labels"]
    relevant = texts[labels.index(1)]
    irrelevant = texts[labels.index(0)]

    def src(kind: str) -> dict:
        return {
            "dataset": "zilliz/gooaq-context-relevance",
            "row": row,
            "field": f"texts ({kind})",
            "scaffold": "response",
        }

    return [
        _single_turn_case(
            f"context-relevance-gooaq-{row}-pass", "context-relevance", "pass",
            rec["query"], _SCAFFOLD_ANSWER, context=relevant, source=src("relevant"),
        ),
        _single_turn_case(
            f"context-relevance-gooaq-{row}-fail", "context-relevance", "fail",
            rec["query"], _SCAFFOLD_ANSWER, context=irrelevant, source=src("irrelevant"),
        ),
    ]


def build_conciseness_cases(dataset) -> list[dict]:
    """daloopa: a concise answer (high conc_rating) passes, a verbose one fails."""

    def case(idx: int, expect: str) -> dict:
        r = dataset[idx]
        return _single_turn_case(
            f"conciseness-daloopa-{idx}-{expect}", "conciseness", expect,
            r["question"], r["answer"],
            source={"dataset": "daloopa/financial-retrieval", "row": idx, "field": "answer"},
        )

    ok = lambda r: bool((r["answer"] or "").strip())  # noqa: E731
    return [
        case(_find_index(dataset, lambda r: ok(r) and r["conc_rating"] >= 4), "pass"),
        case(_find_index(dataset, lambda r: ok(r) and r["conc_rating"] <= 2), "fail"),
    ]


def build_user_frustration_cases(dataset) -> list[dict]:
    """IEMOCAP: a calm user turn passes, a frustrated one fails. The evaluator
    scores the user input; the assistant response is scaffolded."""

    def case(idx: int, expect: str) -> dict:
        r = dataset[idx]
        return _single_turn_case(
            f"user-frustration-iemocap-{idx}-{expect}", "user-frustration", expect,
            r["transcription"].strip(), _SCAFFOLD_FRUSTRATION_ANSWER,
            source={
                "dataset": "AbstractTTS/IEMOCAP",
                "row": idx,
                "field": "transcription",
                "scaffold": "response",
            },
        )

    ok = lambda r: bool((r["transcription"] or "").strip())  # noqa: E731
    return [
        case(_find_index(dataset, lambda r: ok(r) and r["frustrated"] < 0.5), "pass"),
        case(_find_index(dataset, lambda r: ok(r) and r["frustrated"] >= 0.5), "fail"),
    ]


def build_bias_cases(dataset, row: int = 0) -> list[dict]:
    """StereoSet: an anti-stereotype sentence is unbiased (pass), a stereotype
    sentence is biased (fail). The user prompt is scaffolded."""
    rec = dataset[row]
    sentences = rec["sentences"]
    labels = sentences["gold_label"]  # 0=anti-stereotype, 1=stereotype, 2=unrelated
    anti = sentences["sentence"][labels.index(0)]
    stereo = sentences["sentence"][labels.index(1)]

    def src(gold_label: int) -> dict:
        return {
            "dataset": "McGill-NLP/stereoset",
            "row": row,
            "field": "sentences",
            "gold_label": gold_label,
            "scaffold": "user",
        }

    return [
        _single_turn_case(
            f"bias-stereoset-{row}-pass", "bias", "pass",
            _SCAFFOLD_BIAS_USER, anti, source=src(0),
        ),
        _single_turn_case(
            f"bias-stereoset-{row}-fail", "bias", "fail",
            _SCAFFOLD_BIAS_USER, stereo, source=src(1),
        ),
    ]


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


def _load_soda():
    from datasets import Dataset

    matches = glob.glob(
        str(
            Path.home()
            / ".cache/huggingface/datasets/Johndfm___soda_eval/**/soda_eval-train.arrow"
        ),
        recursive=True,
    )
    if not matches:
        raise FileNotFoundError(
            "Johndfm/soda_eval not found in the HF cache. Download it first: "
            "`datasets.load_dataset('Johndfm/soda_eval')`."
        )
    return Dataset.from_file(matches[0])


def _load(cache_dir: str, human_name: str):
    """Load the (train-preferred) arrow file for a cached HF dataset."""
    from datasets import Dataset

    matches = glob.glob(
        str(Path.home() / ".cache/huggingface/datasets" / cache_dir / "**/*.arrow"),
        recursive=True,
    )
    if not matches:
        raise FileNotFoundError(
            f"{human_name} not found in the HF cache. Download it first with "
            f"datasets.load_dataset(...)."
        )
    train = [m for m in matches if "train" in m.lower()]
    return Dataset.from_file(sorted(train or matches)[0])


def build_all() -> dict:
    cases = build_toxicity_cases(_load_hhrlhf())
    cases += build_fluency_cases(_load_soda())
    cases += build_faithfulness_cases(
        _load("Salesforce___faith_eval-counterfactual-v1.0", "FaithEval")
    )
    cases += build_hallucination_cases(
        _load("Cleanlab___fin_qa-hallucination-detection", "FinQA")
    )
    cases += build_relevance_cases(_load("nvidia___help_steer2", "HelpSteer2"))
    cases += build_factual_accuracy_cases(
        _load("domenicrosati___truthful_qa", "TruthfulQA")
    )
    cases += build_answer_completeness_cases(
        _load("Magneto___qa-dataset-llm-judge-flattened", "Magneto")
    )
    cases += build_pii_leakage_cases(_load("nvidia___nemotron-pii", "Nemotron-PII"))
    cases += build_summarization_cases(_load("mteb___summeval", "SummEval"))
    cases += build_prompt_injection_cases(
        _load("neuralchemy___prompt-injection-dataset", "neuralchemy prompt-injection")
    )
    cases += build_context_relevance_cases(_load("zilliz___gooaq*", "gooaq context-relevance"))
    cases += build_conciseness_cases(_load("daloopa___financial-retrieval", "daloopa"))
    cases += build_user_frustration_cases(
        _load("AbstractTTS___*", "IEMOCAP").remove_columns(["audio"])
    )
    cases += build_bias_cases(_load("McGill-NLP___stereoset", "StereoSet"))
    cases = [_attach_model_usage(c) for c in cases]
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
