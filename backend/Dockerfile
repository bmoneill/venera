FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer is cached independently of source changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ephemeris files land here; mount a named volume at /app/data to persist them
RUN mkdir -p /app/data

# Copy the backend package
COPY __init__.py astronomy.py auth.py database.py main.py models.py search.py ./backend/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
