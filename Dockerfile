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

# Render/Railway inject PORT and config.py binds 0.0.0.0 whenever it's set -
# but running this image directly (`docker run -p 8000:8000 ...`, no PORT)
# would otherwise fall back to 127.0.0.1 inside the container, so the port
# mapping looks live but nothing ever answers. Set explicitly so the image
# behaves correctly standalone too; DASHBOARD_HOST/PORT still override this.
ENV DASHBOARD_HOST=0.0.0.0

CMD ["python", "dashboard.py"]
