FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ config/
COPY data/labeled_prompts.csv data/labeled_prompts.csv
COPY src/ src/
COPY scripts/ scripts/
COPY tests/ tests/
COPY frontend/ frontend/
COPY README.md .

# Train the complexity classifier inside the image (joblib is gitignored locally)
RUN python -m src.routing.train_classifier

EXPOSE 8000 8501

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
