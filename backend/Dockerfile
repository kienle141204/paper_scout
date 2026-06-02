FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source — agent package and backend run from project root
COPY agent/ ./agent/
COPY backend/ ./backend/
COPY pyproject.toml ./

# Install the agent package in editable mode so backend can import it
RUN pip install --no-cache-dir -e . --no-deps

ENV PYTHONPATH=/app

WORKDIR /app/backend

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
