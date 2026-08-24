FROM python:3.11-slim

WORKDIR /app

COPY libs/contracts /app/libs/contracts
COPY services/notifier/pyproject.toml /app/services/notifier/
COPY services/notifier/src /app/services/notifier/src

RUN pip install --no-cache-dir /app/libs/contracts \
    && pip install --no-cache-dir /app/services/notifier

WORKDIR /app/services/notifier

CMD ["python", "-m", "notifier"]
