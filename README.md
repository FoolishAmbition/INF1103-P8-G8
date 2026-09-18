EventWise — AI-Assisted Student Event Decision System
1. Problem Statement and Target Users
Students are often invited to career talks, workshops, networking sessions, club activities
and other school events. With assignments, classes and other commitments, it can be
difficult to decide whether an event is worth attending. Students may miss useful
opportunities or spend time on events that are not very relevant to them.
EventWise is a student event decision-making assistant that helps users decide whether
to attend an event based on event details and their current situation. The target users are
university and polytechnic students who regularly receive event invitations and need a
quick way to judge whether an event is worth their time based on the student's own
workload, interest level and other provided circumstances.
2. User Inputs
The system will collect:
• Event name
• Event description
• Event duration (minutes)
• Travel time (minutes)
• Interest level (1–5)
• Current workload (Low / Medium / High)
• Career relevance (Yes / No)
• Additional information, such as event cost or networking opportunities (optional)
• Post-Event Feedback (For events that the user attended, the system will allow the
student to provide feedback after the event, including an overall rating (1–5), what went
well, what was not useful, and whether they would attend a similar event again. (optional) )
All inputs will be validated. Invalid values, such as a negative travel time or an interest
level outside 1–5, will be rejected, and the user will be asked to enter the value again.
3. Use of AI
Every event record will be passed to the AI for analysis. The AI will read the event
description together with the student's inputs and return a structured JSON response.
The output will contain values such as career relevance, learning value, networking value,
event category, and a short reason.
Example:
{ "career_relevance": 4, "learning_value": 5, "networking_value": 4, "event_category":
"Career", "reason": "Useful for students interested in cybersecurity careers." }
The AI is used to understand and score the event, but it will not make the final decision.
The program's logic will use the AI output together with the user's inputs to decide whether
the recommendation is ATTEND, MAYBE or SKIP.
After an attended event, the AI will also analyse the student's post-event feedback to
identify useful preferences or patterns.
4. Business Rules
After the AI returns its analysis, the program will apply rules to produce the final
recommendation. Possible rules include:
• ATTEND if career relevance is at least 4, learning value is at least 4, workload is not
High, and travel time is 60 minutes or less.
• MAYBE if career relevance, learning value or networking value is high, but the student's
workload is High.
• SKIP if interest level is 2 or below and career relevance is 2 or below.
• SKIP if travel time is more than 90 minutes and the event's overall value is low.
• If the AI output is invalid or missing required fields, the system will reject the response
and retry instead of crashing.
• If a student has attended at least 2 similar events and their average rating is ≥4, increase
consideration for similar future events. If at least 2 similar events have an average rating
≤2, decrease consideration.
The final result will show the recommendation and a short reason. The event details, AI
analysis and final decision will then be saved in a JSON file so users can review previous
recommendations.
{
Recommendation: ATTEND
Reason: The event has high career relevance and learning value, and your current
workload is manageable.
}
5. Team Repository Details
GitHub Repository URL: https://github.com/FoolishAmbition/INF1103-P8-G8
