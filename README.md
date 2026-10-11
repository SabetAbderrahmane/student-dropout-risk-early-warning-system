# Student Dropout Risk Early Warning System

Student academic early-warning system using a modular-monolith architecture:

- Next.js frontend
- FastAPI backend
- PostgreSQL with SQLAlchemy 2.x and Alembic
- Argon2 password hashing, JWT access tokens, and backend RBAC
- Student, admission, and first-semester academic record management
- Reproducible offline dropout-model training and selection
- Database-backed student search and pagination
- Docker Compose development environment

Includes runtime predictions, persisted warnings, intervention and follow-up
casework, audit history, and dashboard read models.

## Run with Docker Compose

1. Copy `.env.example` to `.env`.
2. Replace the database password and JWT secret. The JWT secret must contain at least 32 characters.
3. To create the first system administrator, temporarily fill the four `BOOTSTRAP_ADMIN_*` values.
4. Prepare the verified model using the instructions below. The default backend
   build fails if its model is missing, corrupted, or incompatible.
5. Start the stack:

   ```bash
   docker compose up --build
   ```

6. After the account is created, remove `BOOTSTRAP_ADMIN_PASSWORD` from `.env` and restart the backend. The bootstrap command is idempotent and never overwrites an existing account.

Services:

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health
- Process liveness: http://localhost:8000/api/v1/health/live
- Database and ML readiness: http://localhost:8000/api/v1/health/ready

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

## Prepare the deployment model

Prerequisites: Python **3.11.9**, the pinned backend dependencies, and network
access to UCI dataset 697 for offline reproduction. No external model host is
assumed. From a fresh clone, create/activate a Python 3.11.9 virtual environment:

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m app.ml.deployment reproduce
python -m app.ml.deployment verify
```

Reproduction runs the unchanged five-fold candidate selection, development-only
threshold calibration, and held-out evaluation in a temporary directory. It
installs `app/ml/artifacts/dropout-risk-v1/model.joblib` only when the resulting
binary SHA-256 and training records match the tracked registry. It does not
replace the approved registry or silently accept a different model. Training
never runs during API startup or requests.

Then, from the repository root:

```bash
docker compose build backend
docker compose up -d
```

See [model deployment and troubleshooting](docs/ml-model-deployment.md) for exact
dependency versions, trusted-artifact installation, intentional degraded
development, readiness responses, and real PostgreSQL integration verification.

## Frontend development

```bash
cd frontend
npm ci
npm run dev
```
