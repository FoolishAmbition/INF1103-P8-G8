# EventWise 🎓

An AI-assisted decision-support system that helps students evaluate whether academic, career, and networking events are worth attending based on their studies, workload, and transit feasibility.

---

## What is EventWise?

As a tertiary student, you are constantly invited to career talks, technical workshops, hackathons, and networking sessions. Between coursework, exams, and personal commitments, deciding what to attend can be overwhelming.

EventWise connects your student profile, schedule workload, and event details to give you:
- **AI Fit Evaluation:** Analyzes event descriptions with Google Gemini to rate career relevance, learning value, and networking potential.
- **Attendance Recommendation:** Uses deterministic rules to give a clear verdict (**ATTEND**, **MAYBE**, or **SKIP**) tailored to your current workload.
- **Singapore Transit Feasibility:** Integrates with the Singapore OneMap API to calculate public transit routes, journey duration, and recommended departure times so you arrive with time to spare.
- **Searchable History & Insights:** View, filter, and track all your past event decisions and attendance trends directly from your browser.

---

## Setup & Configuration

### 1. Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (recommended for containerized deployment), **OR**
- Python 3.11+ and MongoDB (for running locally).

### 2. Environment Variables (`.env`)
Create a `.env` file in the root directory:

```env
# Required: Google Gemini API key
API_KEY=your_gemini_api_key_here

# Optional: Singapore OneMap Token (for public transit routing)
ONEMAP_ACCESS_TOKEN=your_onemap_token_here

# Optional: MongoDB connection URI (defaults to mongodb://localhost:27017/)
MONGODB_URI=mongodb://localhost:27017/
```

> **Tip:** If you have a Singapore OneMap account, you can automatically fetch and save your token into `.env` by running:
> ```bash
> python get_onemap_token.py
> ```

---

## How to Run the Application

### Option A: Using Docker Compose (Recommended)

Docker Compose automatically spins up both the MongoDB database and the EventWise web interface.

1. **Start the application:**
   ```bash
   docker compose up -d
   ```

2. **Open the web dashboard:**
   Navigate to:
   ```
   http://localhost:5000
   ```

3. **Stop the application:**
   ```bash
   docker compose down
   ```
   *(Your saved data persists safely inside the `mongodb_data` volume).*

---

### Option B: Running Locally (Native Python)

If you prefer running directly on your host machine:

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start MongoDB:**
   Make sure MongoDB is running on `mongodb://localhost:27017/`. You can quickly launch one via Docker:
   ```bash
   docker run -d --name eventwise-mongo -p 27017:27017 -v mongodb_data:/data/db mongo:8.0
   ```

3. **Run the web server:**
   ```bash
   python main.py
   ```

4. **Open the dashboard:**
   Open your browser at `http://localhost:5000`.

---

## Running the Automated Tests

All automated test suites run completely offline with mocked data and require no live API credentials:

```bash
# Run unit and integration test suites
python -m unittest test_models.py test_geolocation.py test_journey_planner.py test_travel_assessment.py test_travel_result.py test_web_profile.py test_web_travel.py

# Run logic manager and business rule tests
python test_logic_manager.py
```

---

## Project Structure Overview

- `main.py`: Flask web server entrypoint and application orchestrator.
- `src/`: Core modules for AI analysis, scoring rules, data storage, and transit calculation.
- `templates/` & `static/`: Web dashboard frontend (HTML layout, CSS styling, and reactive JavaScript).
- `data/`: Local JSON fallback storage for running in environments without MongoDB.
- `get_onemap_token.py`: Standalone CLI helper to authenticate with OneMap.
