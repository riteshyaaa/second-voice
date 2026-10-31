FROM python:3.12-slim
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY infrastructure/scripts ./scripts
ENV PYTHONUNBUFFERED=1 STORAGE_DIR=/data/audio
EXPOSE 8000
CMD ["sh", "-c", "python -m app.core.init_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
# Seed demo account (optional): docker compose exec backend python scripts/seed_demo.py
