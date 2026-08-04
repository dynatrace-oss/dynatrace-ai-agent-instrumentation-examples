"""The validator catches malformed fixtures, and the shipped fixtures.json is
well-formed."""

from pathlib import Path

import pytest
from fixtures import load_fixtures, normalize_case
from validate import assert_valid, validate_cases

FIXTURES_JSON = Path(__file__).resolve().parent.parent / "fixtures.json"


def _case(**overrides):
    base = {
        "name": "ok",
        "targets": ["toxicity"],
        "expect": "fail",
        "turns": [{"user": "hi", "response": "there"}],
    }
    base.update(overrides)
    return normalize_case(base)


def test_valid_case_has_no_errors():
    assert validate_cases([_case()]) == []


def test_duplicate_names_flagged():
    errors = validate_cases([_case(name="dup"), _case(name="dup")])
    assert any("duplicate case name: dup" in e for e in errors)


def test_unknown_target_flagged():
    errors = validate_cases([_case(targets=["not-a-metric"])])
    assert any("unknown evaluator target 'not-a-metric'" in e for e in errors)


def test_invalid_expect_flagged():
    errors = validate_cases([_case(expect="maybe")])
    assert any("invalid expect 'maybe'" in e for e in errors)


def test_context_required_for_faithfulness():
    errors = validate_cases([_case(targets=["faithfulness"])])
    assert any("require a 'context'" in e for e in errors)
    # ...and satisfied once context is present.
    assert validate_cases([_case(targets=["faithfulness"], context="grounding")]) == []


def test_reference_required_for_factual_accuracy():
    errors = validate_cases([_case(targets=["factual-accuracy"])])
    assert any("require a 'reference'" in e for e in errors)


def test_empty_turn_content_flagged():
    errors = validate_cases([_case(turns=[{"user": "", "response": "x"}])])
    assert any("empty user or response" in e for e in errors)


def test_assert_valid_raises_on_bad_case():
    with pytest.raises(ValueError, match="not well-formed"):
        assert_valid([_case(expect="nope")])


def test_shipped_fixtures_are_well_formed():
    _, cases = load_fixtures(FIXTURES_JSON)
    assert validate_cases(cases) == []


def test_shipped_service_name_matches_e2e_contract():
    """The Go e2e suite hardcodes this in its DQL filter and metric lookup, so a
    rename here would surface only as a nightly timeout with no spans found."""
    service_name, _ = load_fixtures(FIXTURES_JSON)
    assert service_name == "dt-evals-fixtures"
