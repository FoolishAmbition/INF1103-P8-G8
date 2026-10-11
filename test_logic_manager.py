"""
Automated test script for EventWise logic_manager.

Runs WITHOUT any live API connection — all AI responses are hardcoded
sample dictionaries matching the schema returned by ai_manager.analyze_event().

Run with:  python test_logic_manager.py
"""

import sys

from src.logic_manager import (
    validate_ai_result,
    calculate_event_value,
    event_priority,
    generate_recommendation,
    generate_reason,
    get_ai_reasoning,
    generate_summary,
)


# ---------------------------------------------------------------------------
# These are HARDCODED SAMPLE AI RESPONSES (no live API required)
# ---------------------------------------------------------------------------
# These are exactly the same schema defined in ai_manager.ANALYSIS_SCHEMA

# Example 1 - Perfect fit — top scores everywhere, & manageable workload
AI_RESPONSE_STRONG = {
    "event_category": "Technical Workshop",
    "career_relevance": 5,
    "learning_value": 5,
    "networking_value": 4,
    "ai_reasoning": "Directly aligns with the student's ICT background and AI interest.",
}

# Example 2 - Borderline — mid-range values
AI_RESPONSE_MEDIUM = {
    "event_category": "General Talk",
    "career_relevance": 3,
    "learning_value": 3,
    "networking_value": 3,
    "ai_reasoning": "Somewhat relevant but not directly aligned.",
}


# Example 3 - Weak - should be skipped regardless of workload
AI_RESPONSE_WEAK = {
    "event_category": "Social Event",
    "career_relevance": 1,
    "learning_value": 1,
    "networking_value": 1,
    "ai_reasoning": "Not relevant to the student's field or interests.",
}
# ---------------------------------------------------------------------------
# These 3 malformed dictionaries simulate bad AI output 
# ---------------------------------------------------------------------------
# Error — missing required fields
AI_RESPONSE_MISSING_FIELDS = {
    "event_category": "Unknown",
    "career_relevance": 4,
    # learning_value missing
    "networking_value": 3,
    "ai_reasoning": "Incomplete response.",
}

# FeedingError — out of range
AI_RESPONSE_OUT_OF_RANGE = {
    "event_category": "Workshop",
    "career_relevance": 9,
    "learning_value": 5,
    "networking_value": 3,
    "ai_reasoning": "Score exceeds maximum.",
}

# Error — wrong type
AI_RESPONSE_WRONG_TYPE = {
    "event_category": "Workshop",
    "career_relevance": "high",
    "learning_value": 5,
    "networking_value": 3,
    "ai_reasoning": "Type mismatch.",
}


# ---------------------------------------------------------------------------
# MINIMAL TEST RUNNER (no pytest dependency required in Docker)
# ---------------------------------------------------------------------------

def run_all_tests():
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]

    passed = 0
    failed = 0
    failures = []

    for name, func in tests:
        try:
            func()
            print(f"PASS  {name}")
            passed += 1
        except AssertionError as exc:
            print(f"FAIL  {name}  ->  {exc}")
            failures.append((name, exc))
            failed += 1
        except Exception as exc:
            print(f"ERROR {name}  ->  {type(exc).__name__}: {exc}")
            failures.append((name, exc))
            failed += 1

    print()
    print(f"{passed} passed, {failed} failed, {len(tests)} total")

    if failures:
        print("\nFailures:")
        for name, exc in failures:
            print(f"  - {name}: {exc}")

    return failed == 0

# ---------------------------------------------------------------------------
# TESTS: validate_ai_result
# ---------------------------------------------------------------------------

def test_validate_ai_result_accepts_well_formed_response():
    assert validate_ai_result(AI_RESPONSE_STRONG) is True


def test_validate_ai_result_accepts_medium_scores():
    assert validate_ai_result(AI_RESPONSE_MEDIUM) is True


def test_validate_ai_result_rejects_missing_score_field():
    assert validate_ai_result(AI_RESPONSE_MISSING_FIELDS) is False


def test_validate_ai_result_rejects_score_above_maximum():
    assert validate_ai_result(AI_RESPONSE_OUT_OF_RANGE) is False


def test_validate_ai_result_rejects_non_integer_score():
    assert validate_ai_result(AI_RESPONSE_WRONG_TYPE) is False


def test_validate_ai_result_rejects_score_below_minimum():
    bad = {
        "event_category": "Workshop",
        "career_relevance": 0,
        "learning_value": 5,
        "networking_value": 3,
        "ai_reasoning": "Below minimum.",
    }
    assert validate_ai_result(bad) is False


def test_validate_ai_result_rejects_boundary_value_six():
    bad = {
        "event_category": "Workshop",
        "career_relevance": 6,
        "learning_value": 5,
        "networking_value": 3,
        "ai_reasoning": "Just above range.",
    }
    assert validate_ai_result(bad) is False


def test_validate_ai_result_accepts_boundary_values_one_and_five():
    boundary = {
        "event_category": "Workshop",
        "career_relevance": 1,
        "learning_value": 5,
        "networking_value": 1,
        "ai_reasoning": "Boundary values.",
    }
    assert validate_ai_result(boundary) is True


def test_validate_ai_result_rejects_float_scores():
    # type(x) is not int catches 3.0 as well as '3'
    bad = {
        "event_category": "Workshop",
        "career_relevance": 3.0,
        "learning_value": 5,
        "networking_value": 3,
        "ai_reasoning": "Float instead of int.",
    }
    assert validate_ai_result(bad) is False

if __name__ == "__main__":
    ok = run_all_tests()
    sys.exit(0 if ok else 1)