"""Pure Hard Constraint rules: language, location, Gap Tolerance."""

from job_finding_assistant.hard_constraints import (
    ConstraintResult,
    evaluate_gap_tolerance,
    evaluate_language,
    evaluate_location,
    overall_hard_constraint,
)
from job_finding_assistant.preferences import GapTolerance, LanguagePreference, Preferences


def test_location_unknown_when_preferences_locations_empty() -> None:
    result = evaluate_location(
        preferences=Preferences(languages=[], locations=[]),
        work_location="Hong Kong",
    )

    assert result == ConstraintResult(outcome="unknown", reason="No acceptable locations set")


def test_location_pass_when_posting_location_is_accepted() -> None:
    result = evaluate_location(
        preferences=Preferences(languages=[], locations=["Hong Kong", "Remote"]),
        work_location="Hong Kong Island",
    )

    assert result.outcome == "pass"
    assert "Hong Kong" in result.reason


def test_location_pass_when_clearly_remote_and_remote_accepted() -> None:
    result = evaluate_location(
        preferences=Preferences(languages=[], locations=["Remote"]),
        work_location="Work from home / Remote",
    )

    assert result.outcome == "pass"
    assert "remote" in result.reason.lower()


def test_location_fail_on_definite_mismatch() -> None:
    result = evaluate_location(
        preferences=Preferences(languages=[], locations=["Hong Kong"]),
        work_location="Singapore",
    )

    assert result.outcome == "fail"
    assert "Singapore" in result.reason


def test_location_unknown_when_posting_location_missing() -> None:
    result = evaluate_location(
        preferences=Preferences(languages=[], locations=["Hong Kong"]),
        work_location=None,
    )

    assert result == ConstraintResult(
        outcome="unknown",
        reason="Work location missing or unclear",
    )


def test_language_unknown_when_preferences_languages_empty() -> None:
    result = evaluate_language(
        preferences=Preferences(languages=[], locations=[]),
        speaking="English",
        writing=None,
    )

    assert result == ConstraintResult(
        outcome="unknown",
        reason="No languages set in Preferences",
    )


def test_language_pass_when_all_required_languages_in_preferences() -> None:
    result = evaluate_language(
        preferences=Preferences(
            languages=[
                LanguagePreference(language="English"),
                LanguagePreference(language="Cantonese"),
            ],
            locations=[],
        ),
        speaking="English and Cantonese required",
        writing="English",
    )

    assert result.outcome == "pass"
    assert "English" in result.reason
    assert "Cantonese" in result.reason


def test_language_fail_when_required_language_missing() -> None:
    result = evaluate_language(
        preferences=Preferences(
            languages=[LanguagePreference(language="English")],
            locations=[],
        ),
        speaking="Cantonese fluent",
        writing=None,
    )

    assert result.outcome == "fail"
    assert "Cantonese" in result.reason


def test_language_pass_when_only_preferred_wording() -> None:
    result = evaluate_language(
        preferences=Preferences(
            languages=[LanguagePreference(language="English")],
            locations=[],
        ),
        speaking="Mandarin preferred",
        writing=None,
    )

    assert result.outcome == "pass"
    assert "No hard language requirements" in result.reason


def test_gap_tolerance_unknown_when_unset() -> None:
    result = evaluate_gap_tolerance(
        preferences=Preferences(languages=[], locations=[], gap_tolerance=None),
        employment_period="3 months",
    )

    assert result == ConstraintResult(outcome="unknown", reason="Gap Tolerance unset")


def test_gap_tolerance_pass_within_semester() -> None:
    result = evaluate_gap_tolerance(
        preferences=Preferences(
            languages=[],
            locations=[],
            gap_tolerance=GapTolerance.SEMESTER,
        ),
        employment_period="Summer internship, 3 months",
    )

    assert result.outcome == "pass"


def test_gap_tolerance_fail_when_permanent_exceeds_year() -> None:
    result = evaluate_gap_tolerance(
        preferences=Preferences(
            languages=[],
            locations=[],
            gap_tolerance=GapTolerance.YEAR,
        ),
        employment_period="Permanent full-time",
    )

    assert result.outcome == "fail"


def test_gap_tolerance_unknown_when_period_unclear() -> None:
    result = evaluate_gap_tolerance(
        preferences=Preferences(
            languages=[],
            locations=[],
            gap_tolerance=GapTolerance.ANY,
        ),
        employment_period="TBC",
    )

    assert result.outcome == "unknown"


def test_overall_fail_if_any_constraint_fails() -> None:
    assert (
        overall_hard_constraint(
            [
                ConstraintResult(outcome="pass", reason="ok"),
                ConstraintResult(outcome="fail", reason="no"),
                ConstraintResult(outcome="unknown", reason="?"),
            ]
        )
        == "fail"
    )


def test_overall_pass_only_when_all_pass() -> None:
    assert (
        overall_hard_constraint(
            [
                ConstraintResult(outcome="pass", reason="a"),
                ConstraintResult(outcome="pass", reason="b"),
            ]
        )
        == "pass"
    )


def test_overall_pass_when_applicable_constraints_pass_and_others_unknown() -> None:
    assert (
        overall_hard_constraint(
            [
                ConstraintResult(outcome="pass", reason="a"),
                ConstraintResult(outcome="unknown", reason="b"),
            ]
        )
        == "pass"
    )


def test_overall_unknown_when_every_constraint_is_unknown() -> None:
    assert (
        overall_hard_constraint(
            [
                ConstraintResult(outcome="unknown", reason="a"),
                ConstraintResult(outcome="unknown", reason="b"),
            ]
        )
        == "unknown"
    )
