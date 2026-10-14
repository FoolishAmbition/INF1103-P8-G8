import random

CAREER_RELEVANCE = {
    1: "Not relevant at all",
    2: "Slightly",
    3: "Somewhat",
    4: "Highly",
    5: "Directly relevant",
}

LEARNING_VALUE = {
    1: "Very little",
    2: "Low",
    3: "Moderate",
    4: "High",
    5: "Very high",
}

NETWORKING_VALUE = {
    1: "Nothing",
    2: "Very limited",
    3: "Some",
    4: "Good",
    5: "Very Strong",
}


# check if the ai_result is valid
def validate_ai_result(ai_result):
    score_limit = ["career_relevance", "learning_value", "networking_value"]
    text_field = ["event_category", "ai_reasoning"]

    # check if score is int and within minimum and maximum
    for key in score_limit:
        val = ai_result.get(key)
        if type(val) is not int or not (1 <= val <= 5):
            return False

    # validate AI text field
    for key in text_field:
        val = ai_result.get(key)
        if not isinstance(val, str) or not val.strip():
            return False

    return True


# event value calculation based on the ai_result
def calculate_event_value(ai_result):
    return (
        ai_result["career_relevance"]
        + ai_result["learning_value"]
        + ai_result["networking_value"]
    )


# categorise event value
def event_priority(event_value):
    if event_value >= 11:
        priority = "High"
    elif 7 <= event_value <= 10:
        priority = "Medium"
    else:
        priority = "Low"
    return priority


# generate recommendation based on the ai_result and workload
def generate_recommendation(ai_result, workload):
    career = ai_result["career_relevance"]
    learning = ai_result["learning_value"]
    event_value = calculate_event_value(ai_result)

    if career >= 4 and learning >= 4 and workload in ("Low", "Medium"):
        return "ATTEND"

    if event_value >= 11 and workload in ("Low", "Medium"):
        return "ATTEND"

    if event_value >= 11 and workload == "High":
        return "MAYBE"

    if event_value >= 8 and workload in ("Low", "Medium"):
        return "MAYBE"

    if event_value >= 8 and workload == "High":
        return "SKIP"

    return "SKIP"


# main logic : generate reason based on the recommendation and workload
def generate_reason(recommendation, workload):
    if recommendation == "ATTEND":
        if workload == "High":
            return (
                "The event offers strong overall value and is worth considering, "
                "but make sure attending will not interfere with your current workload."
            )

        return (
            "The event offers strong overall value and/or particularly strong "
            "career and learning opportunities. Your workload is manageable, "
            "making this a good opportunity to attend."
        )

    if recommendation == "MAYBE":
        if workload == "High":
            return (
                "The event offers potential value, but your current workload "
                "may limit your ability to benefit from it. Consider attending "
                "only if you can manage your existing commitments."
            )

        return (
            "The event offers some worthwhile opportunities, but its overall "
            "value may not justify prioritising it over other commitments. "
            "Consider attending if it aligns with your interests and goals."
        )

    return (
        "The event may not offer sufficient overall value to justify the time "
        "commitment, or your current workload may be too high. It may be better "
        "to prioritise other opportunities or your existing commitments."
    )


def generate_summary(ai_result: dict, workload: int):
    if not validate_ai_result(ai_result):
        return None, "Invalid AI result. Please analyze the event again"

    event_value = calculate_event_value(ai_result)
    recommendation = generate_recommendation(ai_result, workload)

    summary = {
        "event_value": event_value,
        "recommendation": recommendation,
        "priority": event_priority(event_value),
        "reason": generate_reason(recommendation, workload),
    }

    # add ai_result dict contents to summary dict contents
    summary |= ai_result
    return summary, None


def format_scores(career_relevance, learning_value, networking_value):
    return {
        "career_relevance": f"{CAREER_RELEVANCE[career_relevance]} [{career_relevance}/5]",
        "learning_value": f"{LEARNING_VALUE[learning_value]} [{learning_value}/5]",
        "networking_value": f"{NETWORKING_VALUE[networking_value]} [{networking_value}/5]",
    }


def add_dummy_event():
    return {
        "event_category": "Dummy Category",
        "career_relevance": random.randint(1, 5),
        "learning_value": random.randint(1, 5),
        "networking_value": random.randint(1, 5),
        "ai_reasoning": "Dummy AI reasoning",
        "event_name": "Dummy Event Name",
        "event_description": "Dummy Event Description",
        "workload": random.choice(["Low", "Medium", "High"]),
    }


# TEST
if __name__ == "__main__":
    print(
        generate_summary(
            {
                "event_category": "Technical Workshop",
                "career_relevance": 5,
                "learning_value": 5,
                "networking_value": 4,
                "ai_reasoning": "The event directly aligns with the student's ICT Software Engineering background and specific interest in AI by teaching practical production-ready RAG pipelines.",
            },
            1,
        )
    )
