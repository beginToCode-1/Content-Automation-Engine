FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/work /app/config

ENV WORK_DIR=/data/work
ENV DB_PATH=/data/content_engine.db

EXPOSE 8000

CMD ["python", "run.py"]
