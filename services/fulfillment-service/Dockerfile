FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /repo

RUN pip install --no-cache-dir uv

COPY libs/python/dk_common /repo/libs/python/dk_common
COPY services/fulfillment-service /repo/services/fulfillment-service

RUN uv pip install --system /repo/libs/python/dk_common
RUN uv pip install --system /repo/services/fulfillment-service

WORKDIR /repo/services/fulfillment-service

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
