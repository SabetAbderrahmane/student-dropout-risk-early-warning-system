# Student Dropout Risk Early Warning System

Phase 1 and Phase 2 foundation for the locked modular-monolith architecture:

- Next.js frontend
- FastAPI backend
- PostgreSQL with SQLAlchemy 2.x and Alembic
- Argon2 password hashing, JWT access tokens, and backend RBAC
- Docker Compose development environment

Student, import, prediction, warning, intervention, follow-up, and dashboard domains are intentionally not implemented yet.

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

## Backend development

Create a virtual environment, install `backend/requirements-dev.txt`, export the variables from `backend/.env.example`, and run:

```bash
cd backend
alembic upgrade head
python -m app.db.init_db
uvicorn app.main:app --reload
pytest
```

## Frontend development

```bash
cd frontend
npm ci
npm run dev
```

