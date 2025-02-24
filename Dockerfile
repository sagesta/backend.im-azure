# Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/
COPY scripts/ /app/scripts/
COPY config/ /app/config/
COPY deployments/ /app/deployments/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]