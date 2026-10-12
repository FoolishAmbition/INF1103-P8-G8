# Runs a headless test of logic_manager on container start.
# For the interactive app, override the command:
#   docker run --rm -it eventwise python main.py

FROM python:3.11-slim

# Keep Python output unbuffered and don't write .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (leverages Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project (src/, main.py, tests, etc.)
COPY . .

# Default command: run the automated test suite.
# This proves the application runs headless inside the container
# without requiring a live API connection.
CMD ["python", "test_logic_manager.py"]