FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/crashsense \
    YOLO_CONFIG_DIR=/home/crashsense/.config/Ultralytics

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system crashsense \
    && useradd --system --gid crashsense --create-home crashsense \
    && mkdir -p /app/storage/videos /home/crashsense/.config/Ultralytics \
    && chown -R crashsense:crashsense /app/storage /home/crashsense

COPY requirements-prod.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-prod.txt

COPY --chown=crashsense:crashsense app ./app
COPY --chown=crashsense:crashsense migrations ./migrations
COPY --chown=crashsense:crashsense alembic.ini .

USER crashsense
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
