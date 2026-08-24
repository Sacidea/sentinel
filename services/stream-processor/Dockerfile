FROM python:3.11-slim

WORKDIR /app

COPY libs/contracts /app/libs/contracts
COPY services/stream-processor/pyproject.toml /app/services/stream-processor/
COPY services/stream-processor/src /app/services/stream-processor/src

RUN pip install --no-cache-dir /app/libs/contracts \
    && pip install --no-cache-dir /app/services/stream-processor

WORKDIR /app/services/stream-processor

CMD ["python", "-m", "stream_processor"]
