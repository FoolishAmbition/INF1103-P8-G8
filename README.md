EventWise - AI-Assisted Student Event Decision System

1. Problem Statement and Target Users
Students are often invited to career talks, workshops, networking sessions, club activities and other school events. With assignments, classes and other commitments, it can be difficult to decide whether an event is worth attending. Students may miss useful opportunities or spend time on events that are not very relevant to them.

EventWise is a student event decision-making assistant that helps users decide whether to attend an event based on event details and their current situation. The target users are university and polytechnic students who need a quick way to judge whether an event is worth their time based on their workload, field of study, interests and the event information provided.

2. User Inputs and Features
When using the system for the first time, the student creates a profile containing:

- Field of study
- One or more interests

The profile is saved in `data/profile.json` and loaded automatically the next time the program runs. The profile can also be edited from the main menu.

For each event, the user provides:

- Event name
- Event description
- Current workload: Low, Medium or High

The application validates required fields before submission. Users can cancel profile or event input without saving the changes.

The main menu provides the following options:

- Profile - create or edit the saved student profile
- Analyse New Events - analyse an event using Gemini AI
- View Analysed Events - view saved event summaries and details
- Add Dummy Event - add a randomly generated event for demonstration/testing without an API call
- Exit - save current data and close the application

3. Use of AI
Each submitted event is sent to the Google Gemini API together with the student's saved profile. Gemini returns structured JSON containing:

- Event category
- Career relevance score from 1 to 5
- Learning value score from 1 to 5
- Networking value score from 1 to 5
- Short AI reasoning

The response is checked to make sure all required fields are present and valid. The AI does not make the final attendance decision. The program's business rules use the AI scores together with the student's workload to return ATTEND, MAYBE or SKIP.

If the API key is missing, the API request fails, the response is invalid, or a temporary API/network error occurs, the application displays an error. Temporary failures are retried up to three times.

4. Business Rules
The program calculates the event value as:

Event Value = Career Relevance + Learning Value + Networking Value

The minimum event value is 3 and the maximum is 15. Event priority is classified as:

- High: 11-15
- Medium: 7-10
- Low: 3-6

Recommendations are evaluated from top to bottom:

| Condition | Recommendation |
| --- | --- |
| Career relevance >= 4 AND learning value >= 4 AND workload is Low or Medium | ATTEND |
| Event value >= 11 AND workload is Low or Medium | ATTEND |
| Event value >= 11 AND workload is High | MAYBE |
| Event value >= 8 AND workload is Low or Medium | MAYBE |
| Event value >= 8 AND workload is High | SKIP |
| Event value <= 7 | SKIP |

The final recommendation, priority, score breakdown, AI reasoning and a short explanation are displayed to the user. Analysed events are saved in `data/events.json` and can be viewed later.

5. Running the Project

Install the dependencies:

```text
pip install -r requirements.txt
```

Create a `.env` file in the project root and add a Google AI Studio API key:

```text
API_KEY=YOUR_API_KEY_HERE
```

Start the application:

```text
python main.py
```

Run the automated logic tests (no live API connection is required):

```text
python test_logic_manager.py
```

The application stores profile and event history locally in the `data` directory. The files are created automatically when data is saved.

6. Docker

Build and run the application with Docker:

```text
docker build -t eventwise .
docker run -it --env-file .env eventwise
```

7. Team Repository Details
GitHub Repository URL: https://github.com/FoolishAmbition/INF1103-P8-G8

Overall Flow:
User
  |
  v
io_manager.py - collect and validate profile, event and workload input
  |
  v
ai_manager.py - send the profile and event to Gemini and receive structured JSON
  |
  v
logic_manager.py - validate AI output, calculate value, priority and recommendation
  |
  v
data_manager.py - load and save profile and event history
