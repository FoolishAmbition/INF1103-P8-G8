#check if the ai_result is valid
def validate_ai_result(ai_result):
    score_limit = [
        "career_relevance",
        "learning_value",
        "networking_value",
    ]

    text_field = [
        "event_category",
        "ai-reasoning"
    ]
    #check if score is within minimum and maximum
    for scores in score_limit:
        if scores not in ai_result:
            return False
        elif type(ai_result[scores]) is not int:
            return False
        elif ai_result[scores] < 1 or ai_result[scores] > 5:
            return False
    #validate AI text field
    for text in text_field:
        if text not in text_field:
            return "Unknown"
        elif type(ai_result[text]) is not str:
            return "False"
    return True


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

    if career >= 5 and learning >= 4 and 1 <= workload <= 2:
        recommendation = "Attend"
    elif event_value >= 11 and workload == 3:
        recommendation = "Maybe"
    elif event_value >= 11 and 1 <= workload <= 2:
        recommendation = "Attend"
    elif 8 <= event_value <= 10 and 1 <= workload <= 2:
        recommendation = "Attend"
    elif 5 <= event_value <= 7 and workload == 3:
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
            reason = "The event offers valueble opportunities and its worthwhile, but your current workload may limit your ability to attend. Consider attending if possible."
        else:
            reason = "The event offers valueble opportunities and its worthwhile. Since your workload is manageable, consider attending."
    else:
        reason = "The event is not highly relevant to you or your workload is too high to attend. It may be best to skip this event."
    return reason

#give user an explanation of the ai score based on the career_relevance, learning_value, and networking_value scores
def explain_ai_score(ai_result):
    scores = [
        ai_result["career_relevance"],
        ai_result["learning_value"],
        ai_result["networking_value"],
    ]
    categories = [
        "Career Relevance",
        "Learning Value",
        "Networking Value",
    ]
    score_ratings = {}

    for i, category in enumerate(categories):
        score = scores[i]
        if score >= 5:
            rating = "Excellent"
        elif score >= 4:
            rating = "Good"
        elif score >= 3:
            rating = "Average"
        elif score >= 2:
            rating = "Below Average"
        else:
            rating = "Poor"

        score_ratings[category] = {
            "score": score,
            "rating": rating
        }
    return score_ratings

    
#output to be generated
def display_results(result):
    for key, value in result.items():
        if key == "Score_Ratings":
            print("Event Ratings:")
            for category, details in value.items():
                print(f"  {category}: Score = {details['score']}/5, Rating = {details['rating']}")
        else:
            print(f"{key}: {value}")


def output(ai_result, workload):
    if not validate_ai_result(ai_result):
        return {"error": "Invalid AI result. Please ensure all scores are integers between 1 and 5."}
    
    score_ratings = explain_ai_score(ai_result)
    event_value = calculate_event_value(ai_result)
    priority = event_priority(event_value)
    recommendation = generate_recommendation(ai_result, workload)
    reason = generate_reason(recommendation, workload)
    event_category = ai_result["event_category"]
    ai_reasoning = ai_result["ai-reasoning"]

    output = {
        "Event Category": event_category,
        "Score_Ratings": score_ratings,
        "Priority": priority,
        "Recommendation": recommendation,
        "Reason": reason,
        "AI_Reasoning": ai_reasoning,
    }
    return output