"""build_fixtures parses real hh-rlhf transcripts into well-formed toxicity
cases. Uses an injected fake dataset so the test never touches the HF cache."""

from build_fixtures import (
    build_fluency_cases,
    build_toxicity_cases,
    parse_transcript,
)
from fixtures import normalize_case
from validate import validate_cases

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
