FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY libs/python/dk_common /app/libs/python/dk_common
COPY services/kitchen-service /app/services/kitchen-service

WORKDIR /app/services/kitchen-service

RUN uv pip install --system /app/libs/python/dk_common
RUN uv pip install --system .

CMD ["python", "-m", "app.main", "--host", "0.0.0.0", "--port", "8000"]
