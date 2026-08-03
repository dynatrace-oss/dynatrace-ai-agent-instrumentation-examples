"""build_fixtures parses real hh-rlhf transcripts into well-formed toxicity
cases. Uses an injected fake dataset so the test never touches the HF cache."""

from build_fixtures import (
    build_answer_completeness_cases,
    build_factual_accuracy_cases,
    build_faithfulness_cases,
    build_fluency_cases,
    build_hallucination_cases,
    build_relevance_cases,
    build_toxicity_cases,
    parse_transcript,
)
from fixtures import normalize_case
from validate import validate_cases


def _well_formed(cases):
    return validate_cases([normalize_case(c) for c in cases]) == []

# Shape of an hh-rlhf harmless-base row: same prefix, differing final assistant.
_PREFIX = "\n\nHuman: What is vulgar language?\n\nAssistant: Language that is offensive."
_FAKE = [
    None,  # padding so index 1 is the real record
    {
        "chosen": _PREFIX + "\n\nHuman: Give an example.\n\nAssistant: I'd rather not say it aloud.",
        "rejected": _PREFIX + "\n\nHuman: Give an example.\n\nAssistant: You dumb idiot, go away.",
    },
]


def test_parse_transcript_yields_ordered_turn_pairs():
    pairs = parse_transcript(_FAKE[1]["chosen"])
    assert pairs == [
        ("What is vulgar language?", "Language that is offensive."),
        ("Give an example.", "I'd rather not say it aloud."),
    ]


def test_build_toxicity_yields_matched_pass_fail_pair():
    cases = build_toxicity_cases(_FAKE, rows=[1])

    assert [c["name"] for c in cases] == [
        "toxicity-hhrlhf-1-pass",
        "toxicity-hhrlhf-1-fail",
    ]
    passes = cases[0]
    fails = cases[1]
    assert passes["expect"] == "pass" and fails["expect"] == "fail"
    # The differing final assistant turn carries the verdict tag.
    assert passes["turns"][-1]["expect"] == "pass"
    assert passes["turns"][-1]["targets"] == ["toxicity"]
    # Multi-turn: two turns each, shared benign prefix.
    assert len(passes["turns"]) == 2
    assert passes["turns"][0] == fails["turns"][0]
    # Provenance recorded for attribution.
    assert fails["source"]["dataset"] == "Anthropic/hh-rlhf"
    assert fails["source"]["field"] == "rejected"


def test_built_toxicity_cases_are_well_formed():
    cases = build_toxicity_cases(_FAKE, rows=[1])
    normalized = [normalize_case(c) for c in cases]
    assert validate_cases(normalized) == []


# soda_eval row shape: speaker-prefixed history lines + an evaluated response.
_SODA = {
    10: {
        "dialog_history": "Ashli: Glad you left him.\nZavian: I know, took me long.\nAshli: Don't be sorry.",
        "response": "Zavian: I feel better thanks to you.",
    },
    20: {
        "dialog_history": "Eleazar: Nice to meet you.\nSharod: My pleasure.\nEleazar: What brings you to town?",
        "response": "Eleazar: Oh right, the conference! Nice to finally put a face to the name.",
    },
}


def test_build_fluency_strips_speakers_and_pairs_turns():
    cases = build_fluency_cases(_SODA, rows={"pass": [10], "fail": [20]})

    assert [c["name"] for c in cases] == ["fluency-soda-10-pass", "fluency-soda-20-fail"]
    passes = cases[0]
    # 4 utterances -> 2 turns; speaker labels stripped.
    assert len(passes["turns"]) == 2
    assert passes["turns"][0]["user"] == "Glad you left him."
    assert passes["turns"][0]["response"] == "I know, took me long."
    assert passes["turns"][-1]["response"] == "I feel better thanks to you."
    assert passes["turns"][-1]["expect"] == "pass"
    assert passes["turns"][-1]["targets"] == ["fluency"]
    assert cases[1]["expect"] == "fail"


def test_built_fluency_cases_are_well_formed():
    cases = build_fluency_cases(_SODA, rows={"pass": [10], "fail": [20]})
    assert validate_cases([normalize_case(c) for c in cases]) == []


# --- single-turn evaluators -------------------------------------------------


def test_faithfulness_pass_follows_context_fail_does_not():
    ds = [
        {
            "question": "Q?",
            "answerKey": "B",
            "choices": '{"label": ["A", "B"], "text": ["wrong", "grounded"]}',
            "context": "the context",
        }
    ]
    cases = build_faithfulness_cases(ds, row=0)
    assert cases[0]["turns"][0]["response"] == "grounded"  # answerKey B
    assert cases[1]["turns"][0]["response"] == "wrong"
    assert cases[0]["context"] == "the context"  # context carried
    assert _well_formed(cases)


def test_hallucination_selects_grounded_and_hallucinated_rows():
    ds = [
        {"query": "q0", "context": "c", "llm_response": "r0", "is_correct": 0},
        {"query": "q1", "context": "c", "llm_response": "r1", "is_correct": 1},
    ]
    cases = build_hallucination_cases(ds)
    assert [c["expect"] for c in cases] == ["pass", "fail"]
    assert cases[0]["turns"][0]["response"] == "r1"  # is_correct==1
    assert all(c["context"] == "c" for c in cases)
    assert _well_formed(cases)


def test_relevance_selects_by_helpfulness():
    ds = [
        {"prompt": "p0", "response": "r0", "helpfulness": 1},
        {"prompt": "p1", "response": "r1", "helpfulness": 4},
    ]
    cases = build_relevance_cases(ds)
    assert cases[0]["turns"][0]["response"] == "r1"  # helpfulness>=4 -> pass
    assert cases[1]["turns"][0]["response"] == "r0"
    assert _well_formed(cases)


def test_factual_accuracy_uses_best_and_incorrect_with_reference():
    ds = [
        {
            "Question": "Q?",
            "Best Answer": "the truth",
            "Incorrect Answers": "a lie; another lie",
        }
    ]
    cases = build_factual_accuracy_cases(ds, row=0)
    assert cases[0]["turns"][0]["response"] == "the truth"
    assert cases[1]["turns"][0]["response"] == "a lie"
    assert all(c["reference"] == "the truth" for c in cases)  # reference carried
    assert _well_formed(cases)


def test_answer_completeness_selects_complete_and_incomplete():
    ds = [
        {"question": "q0", "answer": "a0", "evaluation_completeness": "INCOMPLETE"},
        {"question": "q1", "answer": "a1", "evaluation_completeness": "COMPLETE"},
    ]
    cases = build_answer_completeness_cases(ds)
    assert cases[0]["turns"][0]["response"] == "a1"  # COMPLETE -> pass
    assert cases[1]["turns"][0]["response"] == "a0"
    assert _well_formed(cases)
