FROM python:3.11-slim

WORKDIR /app

# Once bagimliliklari kopyala (cache katmani)
COPY libs/contracts /app/libs/contracts
COPY services/simulator/pyproject.toml /app/services/simulator/
COPY services/simulator/src /app/services/simulator/src

RUN pip install --no-cache-dir /app/libs/contracts \
    && pip install --no-cache-dir /app/services/simulator

WORKDIR /app/services/simulator

CMD ["python", "-m", "simulator"]
