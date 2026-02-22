# Testing and Local Setup

This guide walks you through setting up a local environment and testing the AI Risk Engine application, from creating a virtual environment to verifying the health router.

**Last updated:** February 21, 2026 (Phase 8 — scalability, load and chaos tests)

---

## Prerequisites

- **Python 3.11+** (3.12 or 3.14 recommended)
- **pip**
- (Optional) **Docker & Docker Compose** — for running Postgres, Redis, and RabbitMQ locally

---

## 1. Clone and enter the project

```bash
cd /path/to/ai_risk_engine
```

---

## 2. Create a virtual environment

Create a venv in the project root (e.g. `venv` or `.venv`). The project `.gitignore` ignores both `venv/` and `.venv/`.

**Linux / macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**Windows (PowerShell):**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

You should see `(venv)` (or similar) in your shell prompt when the environment is active.

---

## 3. Install dependencies

From the project root with the venv activated:

```bash
pip install -e .
```

This installs the package in editable mode with all dependencies from `pyproject.toml` (the canonical dependency definition). For development and testing, optional dev dependencies are included (e.g. pytest, httpx).

---

## 4. Environment variables

The app loads configuration from environment variables and from a `.env` file in the project root. **Do not commit `.env`**; it is listed in `.gitignore`. You can copy `.env.example` to `.env` and fill in the values.

Required variables (see `app/config/settings.py`):

| Variable | Description | Example (local) |
|----------|-------------|-----------------|
| `JWT_SECRET` | Secret for JWT; must be at least 32 characters | `your-super-secret-key-at-least-32-chars-long` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://compliance_user:compliance_pass@localhost:5432/compliance_db` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `RABBITMQ_URL` | RabbitMQ connection URL | `amqp://admin:admin123@localhost:5672/` (see note below) |

Optional (defaults in parentheses):

- `ENVIRONMENT` — `dev` \| `test` \| `prod` (default: `dev`)
- `DEBUG` — `true` \| `false` (default: `false`)
- `LOG_LEVEL` — `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` (default: `INFO`)

**Note:** `docker-compose.yml` configures RabbitMQ with user `admin` and password `admin123`. Use `RABBITMQ_URL=amqp://admin:admin123@localhost:5672/` when using that stack. The `.env.example` uses `guest:guest`; change to match the compose credentials if you use Docker.

Create a `.env` file in the project root, for example:

```env
JWT_SECRET=your-super-secret-key-at-least-32-chars-long
DATABASE_URL=postgresql+asyncpg://compliance_user:compliance_pass@localhost:5432/compliance_db
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://admin:admin123@localhost:5672/
ENVIRONMENT=dev
LOG_LEVEL=INFO
```

To use the default Postgres and Redis from `docker-compose.yml`, start the stack first (see step 5). The health endpoint does **not** connect to the database or Redis; it only reads settings. So the app will start and serve `/health` even if Postgres/Redis are not running, as long as the URLs are set (they are only used when code actually connects).

---

## 5. (Optional) Start local services with Docker Compose

If you want a full local stack (Postgres, RabbitMQ, Redis) as defined in `docker-compose.yml`:

```bash
docker compose up -d
```

**Apply the database schema (required when using Postgres):** After the stack is up, run the authoritative bootstrap migration once so the database has the correct schema:

```bash
docker exec -i compliance_postgres \
  psql -U compliance_user -d compliance_db \
  < app/migrations/001_initial_schema.sql
```

Run this from the **project root** so the path to `app/migrations/001_initial_schema.sql` is correct. The Postgres container name is `compliance_postgres` as defined in `docker-compose.yml`.

Then use the same credentials in `.env` as in the compose file: Postgres (`compliance_user` / `compliance_pass` / `compliance_db`), Redis (`redis://localhost:6379/0`), and RabbitMQ (`amqp://admin:admin123@localhost:5672/`). If you only need to hit the health router, you can skip this step and use the `.env` above; the app will start and `/health` will respond.

---

## 6. Run the application

From the project root with the venv activated:

```bash
uvicorn app.main:app --reload
```

- `--reload` restarts the server when you change code (useful during development).
- Default host is `127.0.0.1` and port is `8000`.

You should see log output indicating the server is running, e.g.:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process ...
```

---

## 7. Check the health router locally

The health router is mounted at **`GET /health`** and returns application status, environment, and version.

**Using curl:**

```bash
curl http://127.0.0.1:8000/health
```

Expected response (example):

```json
{
  "status": "ok",
  "environment": "dev",
  "version": "0.1.0"
}
```

**Using a browser:** open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

**Optional headers:** the app supports `X-Correlation-ID` and `X-Tenant-ID`; they are logged and echoed back in the response. Example:

```bash
curl -H "X-Correlation-ID: my-test-123" -H "X-Tenant-ID: tenant-a" http://127.0.0.1:8000/health
```

---

## 8. Interactive API docs

With the server running:

- **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

You can call `/health` (and other routes) from the Swagger UI.

---

## 9. Verify infrastructure (optional)

From the project root with the venv activated, you can verify connectivity by running the test suite (`pytest tests/`) and by calling the health endpoint once the app and services are up (see **Run the application** and **Health check** below).

Ensure Docker services are up and `.env` is set before running these.

---

## 10. Run tests

The project has test directories under `tests/` (`unit/`, `integration/`, `load/`, `chaos/`). Run tests from the project root with the venv activated. Use **`python -m pytest`** so the correct environment is used:

```bash
# All unit tests
python -m pytest tests/unit/

# Load tests (Phase 8): concurrent workflow and API; multi-tenant; no cross-tenant leakage
python -m pytest tests/load/ -v

# Chaos tests (Phase 8): Redis/messaging/workflow/circuit-breaker failure scenarios; graceful degradation
python -m pytest tests/chaos/ -v

# Full suite (unit + load + chaos)
python -m pytest tests/unit/ tests/load/ tests/chaos/ -v
```

Examples for specific areas:

```bash
# Observability + workflows (Phase 6 & 7)
python -m pytest tests/unit/observability tests/unit/workflows -v
# Scalability (Phase 8)
python -m pytest tests/unit/scalability/ -v
# Application layer (Phase 4)
python -m pytest tests/unit/application/ -v
```

---

## Quick reference

| Step | Command / action |
|------|-------------------|
| Create venv | `python3 -m venv venv` |
| Activate venv (Unix) | `source venv/bin/activate` |
| Install deps | `pip install -e .` (from `pyproject.toml`) |
| Configure | Create `.env` with `JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL` |
| Optional services | `docker compose up -d` |
| Apply schema (after services) | `docker exec -i compliance_postgres psql -U compliance_user -d compliance_db < app/migrations/001_initial_schema.sql` |
| Run app | `uvicorn app.main:app --reload` |
| Health check | `curl http://127.0.0.1:8000/health` |
| API docs | http://127.0.0.1:8000/docs |

---

## Related documentation

- [FOLDER_AND_FILE_STRUCTURE.md](./FOLDER_AND_FILE_STRUCTURE.md) — Full project tree and file roles
- [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) — Project layout and conventions
