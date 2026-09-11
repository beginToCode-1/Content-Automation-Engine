FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/work /app/config

# Defaults to the image's own (ephemeral) filesystem. Override WORK_DIR/DB_PATH
# to an absolute path under a mounted volume (e.g. /data/work) once you attach
# persistent storage - see render.yaml / README's deployment section.

EXPOSE 8000

CMD ["python", "dashboard.py"]
