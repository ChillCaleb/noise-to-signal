FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY adapter_input.py .
COPY llm_layer.py .
COPY main.py .
COPY nlp_layer.py .
COPY url_ingest.py .
COPY api ./api

EXPOSE 8080

CMD ["sh", "-c", "python -m uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8080}"]

