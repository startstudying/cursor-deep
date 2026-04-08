FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements-server.txt ./
RUN pip install --no-cache-dir -r requirements-server.txt

COPY app ./app
COPY services ./services
COPY storage ./storage

EXPOSE 8787

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787", "--proxy-headers", "--forwarded-allow-ips=*"]
