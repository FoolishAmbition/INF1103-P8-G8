"""
Automated test script for EventWise logic_manager.

Runs WITHOUT any live API connection — all AI responses are hardcoded
sample dictionaries matching the schema returned by ai_manager.analyze_event().

Run with:  python test_logic_manager.py
"""

import sys
import os

#Make `src/` importable regardless of where the script is run from (allows test run inside Docker container)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from logic_manager import (
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
# Malformed dictionaries simulating bad AI output 
# ---------------------------------------------------------------------------

# Error — missing required fields
AI_RESPONSE_MISSING_FIELDS = {
    "event_category": "Unknown",
    "career_relevance": 4,
    # learning_value missing
    "networking_value": 3,
    "ai_reasoning": "Incomplete response.",
}

# Error — out of range
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

# ---------------------------------------------------------------------------
# TESTS: calculate_event_value
# ---------------------------------------------------------------------------

def test_calculate_event_value_sums_three_scores():
    # 5 + 5 + 4 = 14
    assert calculate_event_value(AI_RESPONSE_STRONG) == 14


def test_calculate_event_value_medium_response():
    # 3 + 3 + 3 = 9
    assert calculate_event_value(AI_RESPONSE_MEDIUM) == 9


def test_calculate_event_value_weak_response():
    # 1 + 1 + 1 = 3
    assert calculate_event_value(AI_RESPONSE_WEAK) == 3


def test_calculate_event_value_minimum_possible():
    # 1 + 1 + 1 = 3 (documented minimum in README)
    minimum = {
        "career_relevance": 1,
        "learning_value": 1,
        "networking_value": 1,
    }
    assert calculate_event_value(minimum) == 3


def test_calculate_event_value_maximum_possible():
    # 5 + 5 + 5 = 15 (documented maximum in README)
    maximum = {
        "career_relevance": 5,
        "learning_value": 5,
        "networking_value": 5,
    }
    assert calculate_event_value(maximum) == 15


def test_calculate_event_value_ignores_extra_fields():
    # event_category / ai_reasoning must NOT affect the sum
    extended = {
        "event_category": "Workshop",
        "career_relevance": 4,
        "learning_value": 3,
        "networking_value": 2,
        "ai_reasoning": "Some reason.",
        "some_future_field": "ignored",
    }
    assert calculate_event_value(extended) == 9



# ---------------------------------------------------------------------------
# TESTS: event_priority
# ---------------------------------------------------------------------------

def test_event_priority_high_at_minimum_threshold():
    # 11 is the first High value
    assert event_priority(11) == "High"


def test_event_priority_high_at_maximum_value():
    # 15 is the maximum possible event value
    assert event_priority(15) == "High"


def test_event_priority_medium_at_lower_boundary():
    # 7 is the first Medium value
    assert event_priority(7) == "Medium"


def test_event_priority_medium_at_upper_boundary():
    # 10 is the last Medium value
    assert event_priority(10) == "Medium"


def test_event_priority_medium_in_middle():
    assert event_priority(8) == "Medium"


def test_event_priority_low_at_six():
    # 6 is one below the Medium threshold
    assert event_priority(6) == "Low"


def test_event_priority_low_at_minimum_value():
    # 3 is the documented minimum
    assert event_priority(3) == "Low"


def test_event_priority_boundaries_are_not_overlapping():
    # Ensure 10 -> Medium and 11 -> High (the classic off-by-one test)
    assert event_priority(10) == "Medium"
    assert event_priority(11) == "High"

# ---------------------------------------------------------------------------
# TESTS: generate_recommendation  (Rules 1-6 from README)
# ---------------------------------------------------------------------------
# Workload convention: 1 = Low, 2 = Medium, 3 = High
# (matches io_manager.get_event_information's questionary values)

def test_recommendation_rule1_top_scores_low_workload_attend():
    # Rule 1: career >= 4 AND learning >= 4 AND workload in {1,2}
    assert generate_recommendation(AI_RESPONSE_STRONG, 1) == "Attend"


def test_recommendation_rule1_top_scores_medium_workload_attend():
    assert generate_recommendation(AI_RESPONSE_STRONG, 2) == "Attend"


def test_recommendation_rule2_high_value_high_workload_maybe():
    # Rule 2: event_value >= 11 AND workload == 3
    # STRONG: career=5, learning=5 → Rule 1 blocked because workload=3
    # event_value = 14 → falls to Rule 2 → Maybe
    assert generate_recommendation(AI_RESPONSE_STRONG, 3) == "Maybe"

def test_recommendation_rule3_high_value_low_workload_attend():
    # Rule 3: event_value >= 11 AND workload in {1,2}
    # Use a case that does NOT satisfy Rule 1: career < 4
    ai = {
        "event_category": "Networking Night",
        "career_relevance": 3,
        "learning_value": 4,
        "networking_value": 5,      # sum = 12
        "ai_reasoning": "Strong networking, moderate career relevance.",
    }
    assert generate_recommendation(ai, 1) == "Attend"


def test_recommendation_rule4_mid_value_low_workload_maybe():
    # Rule 4: event_value 7-10 AND workload in {1,2}
    # MEDIUM: 3+3+3 = 9
    assert generate_recommendation(AI_RESPONSE_MEDIUM, 1) == "Maybe"


def test_recommendation_rule5_mid_value_high_workload_maybe():
    # Rule 5: event_value 7-10 AND workload == 3
    assert generate_recommendation(AI_RESPONSE_MEDIUM, 3) == "Maybe"


def test_recommendation_rule6_low_value_skip():
    # Rule 6: event_value 3-6 → Skip, regardless of workload
    # WEAK: 1+1+1 = 3
    assert generate_recommendation(AI_RESPONSE_WEAK, 1) == "Skip"


def test_recommendation_rule6_low_value_skip_medium_workload():
    assert generate_recommendation(AI_RESPONSE_WEAK, 2) == "Skip"


def test_recommendation_rule6_low_value_skip_high_workload():
    assert generate_recommendation(AI_RESPONSE_WEAK, 3) == "Skip"


def test_recommendation_rule1_requires_both_thresholds():
    # career >= 4 but learning < 4 → Rule 1 must NOT fire.
    # event_value = 4+3+4 = 11 → Rule 3 fires → Attend
    ai = {
        "event_category": "Workshop",
        "career_relevance": 4,
        "learning_value": 3,
        "networking_value": 4,
        "ai_reasoning": "High career, moderate learning.",
    }
    assert generate_recommendation(ai, 1) == "Attend"

# ---------------------------------------------------------------------------
# TESTS: generate_reason
# ---------------------------------------------------------------------------

def test_generate_reason_attend():
    reason = generate_reason("Attend", 1)
    assert isinstance(reason, str)
    assert "highly relevant" in reason.lower()


def test_generate_reason_maybe_with_high_workload_mentions_heavy():
    reason = generate_reason("Maybe", 3)
    assert isinstance(reason, str)
    assert "heavy" in reason.lower()


def test_generate_reason_maybe_with_low_workload_mentions_manageable():
    reason = generate_reason("Maybe", 1)
    assert isinstance(reason, str)
    assert "manageable" in reason.lower()


def test_generate_reason_skip():
    reason = generate_reason("Skip", 1)
    assert isinstance(reason, str)
    assert "not highly relevant" in reason.lower()


def test_generate_reason_returns_distinct_text_per_branch():
    attend = generate_reason("Attend", 1)
    maybe_heavy = generate_reason("Maybe", 3)
    maybe_light = generate_reason("Maybe", 1)
    skip = generate_reason("Skip", 1)
    assert len({attend, maybe_heavy, maybe_light, skip}) == 4


# ---------------------------------------------------------------------------
# TESTS: get_ai_reasoning
# ---------------------------------------------------------------------------
# Bug fix in commit "fix get_ai_reasoning key mismatch found by test suite":
# the function was originally looking for "ai-reasoning" (hyphen), but the
# AI schema returns "ai_reasoning" (underscore). Tests updated to match the corrected behaviour.

def test_get_ai_reasoning_returns_text_for_real_ai_response():
    # Real AI responses use the underscore key → function returns the string
    result = get_ai_reasoning(AI_RESPONSE_STRONG)
    assert result == AI_RESPONSE_STRONG["ai_reasoning"]


def test_get_ai_reasoning_returns_default_when_key_missing():
    payload = {
        "event_category": "Workshop",
        "career_relevance": 4,
        "learning_value": 4,
        "networking_value": 4,
        # ai_reasoning intentionally missing
    }
    assert get_ai_reasoning(payload) == "No reasoning provided."


def test_get_ai_reasoning_rejects_non_string_value():
    payload = {"ai_reasoning": 12345}
    assert get_ai_reasoning(payload) == "Invalid reasoning format."

# ---------------------------------------------------------------------------
# TESTS: generate_summary
# ---------------------------------------------------------------------------

def test_generate_summary_rejects_invalid_ai_result():
    result = generate_summary(AI_RESPONSE_MISSING_FIELDS, 1)
    assert isinstance(result, str)
    assert "invalid" in result.lower()


def test_generate_summary_returns_dict_for_valid_input():
    result = generate_summary(AI_RESPONSE_STRONG, 1)
    assert isinstance(result, dict)


def test_generate_summary_contains_all_summary_fields():
    result = generate_summary(AI_RESPONSE_STRONG, 1)
    for key in ("event_value", "priority", "recommendation", "reason"):
        assert key in result, f"missing summary key: {key}"


def test_generate_summary_contains_all_ai_fields():
    result = generate_summary(AI_RESPONSE_STRONG, 1)
    for key in (
        "event_category",
        "career_relevance",
        "learning_value",
        "networking_value",
        "ai_reasoning",
    ):
        assert key in result, f"missing AI key: {key}"


def test_generate_summary_values_are_consistent_with_helpers():
    result = generate_summary(AI_RESPONSE_STRONG, 1)
    assert result["event_value"] == calculate_event_value(AI_RESPONSE_STRONG)
    assert result["priority"] == event_priority(result["event_value"])
    assert result["recommendation"] == generate_recommendation(AI_RESPONSE_STRONG, 1)
    assert result["reason"] == generate_reason(result["recommendation"], 1)


def test_generate_summary_priority_high_for_top_response():
    result = generate_summary(AI_RESPONSE_STRONG, 1)
    assert result["priority"] == "High"
    assert result["recommendation"] == "Attend"


def test_generate_summary_priority_low_for_weak_response():
    result = generate_summary(AI_RESPONSE_WEAK, 1)
    assert result["priority"] == "Low"
    assert result["recommendation"] == "Skip"


def test_generate_summary_recommendation_depends_on_workload():
    # Same AI scores, different workload → different recommendation
    low_workload = generate_summary(AI_RESPONSE_STRONG, 1)
    high_workload = generate_summary(AI_RESPONSE_STRONG, 3)
    assert low_workload["recommendation"] == "Attend"
    assert high_workload["recommendation"] == "Maybe"

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


if __name__ == "__main__":
    ok = run_all_tests()
    sys.exit(0 if ok else 1)