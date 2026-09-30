# Student Dropout Risk Early Warning System

Phase 1 through Phase 5A implementation for the locked modular-monolith architecture:

- Next.js frontend
- FastAPI backend
- PostgreSQL with SQLAlchemy 2.x and Alembic
- Argon2 password hashing, JWT access tokens, and backend RBAC
- Student, admission, and first-semester academic record management
- Reproducible offline dropout-model training and selection
- Database-backed student search and pagination
- Docker Compose development environment

Runtime prediction, warning, intervention, follow-up, audit, and dashboard domains are intentionally not implemented yet.

## Run with Docker Compose

1. Copy `.env.example` to `.env`.
2. Replace the database password and JWT secret. The JWT secret must contain at least 32 characters.
3. To create the first system administrator, temporarily fill the four `BOOTSTRAP_ADMIN_*` values.
4. Start the stack:

   ```bash
   docker compose up --build
   ```

5. After the account is created, remove `BOOTSTRAP_ADMIN_PASSWORD` from `.env` and restart the backend. The bootstrap command is idempotent and never overwrites an existing account.

Services:

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health

## API authentication

Login accepts JSON. The `username` field may contain either the account username or email address.

```json
{
  "username": "admin",
  "password": "your-password"
}
```

Use the returned token as `Authorization: Bearer <access_token>`.

Student read endpoints allow all three roles. Student creation, editing, deletion, admission updates, and first-semester updates are restricted to `ACADEMIC_ADMIN`. Student deletion deliberately cascades to its admission and first-semester records at both the ORM and PostgreSQL foreign-key levels.

## Backend development

Create a virtual environment, install `backend/requirements-dev.txt`, export the variables from `backend/.env.example`, and run:

```bash
cd backend
alembic upgrade head
python -m app.db.init_db
uvicorn app.main:app --reload
pytest
```

## Offline ML training

Install the backend development dependencies, then retrieve UCI dataset 697 and run
the full leakage-safe model-selection pipeline:

```bash
cd backend
python -m app.ml.training.train
```

The command evaluates Logistic Regression, Random Forest, and XGBoost with a
stratified five-fold development search, calibrates risk thresholds from
out-of-fold development predictions, and evaluates the selected frozen pipeline
once on the held-out 20% final test set. Generated versioned files are written to
`backend/app/ml/artifacts/dropout-risk-v1/` and remain ignored by Git.

## Frontend development

```bash
cd frontend
npm ci
npm run dev
```
