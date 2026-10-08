#check if the ai_result is valid
def validate_ai_result(ai_result):
    score_limit = [
        "career_relevance",
        "learning_value",
        "networking_value",
    ]


    for scores in score_limit:
        if scores not in ai_result:
            return False
        elif type(ai_result[scores]) is not int:
            return False
        elif ai_result[scores] < 1 or ai_result[scores] > 5:
            return False
    return True

def get_ai_reasoning(ai_reasoning):
    if "ai-reasoning" not in ai_reasoning:
        return "No reasoning provided."
    elif type(ai_reasoning["ai-reasoning"]) is not str:
        return "Invalid reasoning format."
    else:
        return ai_reasoning["ai-reasoning"]


#event value calculation based on the ai_result
def calculate_event_value(ai_result):
    career_relevance = ai_result["career_relevance"]
    learning_value = ai_result["learning_value"]
    networking_value = ai_result["networking_value"]

    event_value = career_relevance + learning_value + networking_value
    return event_value


#categorise event value
def event_priority(event_value):
    if event_value >= 11:
        priority = "High"
    elif 7 <= event_value <= 10:
        priority = "Medium"
    else:
        priority = "Low"
    return priority


#generate recommendation based on the ai_result and workload
def generate_recommendation(ai_result, workload):
    career = ai_result["career_relevance"]
    learning = ai_result["learning_value"]
    event_value = calculate_event_value(ai_result)

    if career >= 4 and learning >= 4 and 1 <= workload <= 2:
        recommendation = "Attend"
    elif event_value >= 11 and workload == 3:
        recommendation = "Maybe"
    elif event_value >= 11 and 1 <= workload <= 2:
        recommendation = "Attend"
    elif 7 <= event_value <= 10 and 1 <= workload <= 2:
        recommendation = "Maybe"
    elif 7 <= event_value <= 10 and workload ==3:
        recommendation = "Maybe"
    else:
        recommendation = "Skip"
    return recommendation

#main logic : generate reason based on the recommendation and workload
def generate_reason(recommendation, workload):
    if recommendation == "Attend":
        reason = "The event is highly relevant to your career and learning goals, and your workload is manageable."
    elif recommendation == "Maybe":
        if workload == 3:
            reason = "The event has a solid potential depending on your focus, but your workload is heavy. Consider attending if possible."
        else:
            reason = "The event has a solid potential depending on your focus, and your workload is manageable. You may consider attending."
    else:
        reason = "The event is not highly relevant to you or your workload is too high to attend. It may be best to skip this event."
    return reason

#output to be generated
def generate_summary(ai_result, workload):
    event_value = calculate_event_value(ai_result)
    priority = event_priority(event_value)
    recommendation = generate_recommendation(ai_result, workload)
    reason = generate_reason(recommendation, workload)
    ai_reasoning = get_ai_reasoning(ai_result)

    if not validate_ai_result(ai_result):
        return "Invalid AI result. Please check the input data."

    summary = {
        "Event_value": event_value,
        "Priority": priority,
        "Recommendation": recommendation,
        "Reason": reason,
        "AI_Reasoning": ai_reasoning
    }
    return summary