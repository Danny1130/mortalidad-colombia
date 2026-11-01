# Imagen para Railway, Google Cloud Run, App Engine o Docker en cualquier PaaS.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8050

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8050
CMD ["sh", "-c", "gunicorn app:server -b 0.0.0.0:${PORT} --timeout 120 --workers 1 --threads 4"]
