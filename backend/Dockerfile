FROM python:3.11.9-slim AS development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

RUN chown -R app:app /app
USER app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m app.db.init_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# The default deployment target must already contain the trusted artifact.
# Use --target development only for intentionally degraded local development.
FROM development AS runtime
ENV ML_MODEL_REQUIRED=true
RUN python -m app.ml.deployment verify
