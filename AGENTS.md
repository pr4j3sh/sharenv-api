# AGENTS.md

FastAPI + async MongoDB (PyMongo) API for managing projects, environments, and variables. Python 3.15, managed with `uv`.

## Setup and commands

- `cp .env.example .env` and set `JWT_SECRET` (e.g. `openssl rand -hex 32`). `settings` is instantiated at import time, so a missing or blank `JWT_SECRET` breaks every command, not just server startup.
- `uv sync` installs deps; `uv add <pkg>` updates `pyproject.toml` and `uv.lock`.
- Run the dev server with `uv run fastapi dev` (auto-detects `app/main.py`, reload enabled, docs at `/docs`). Run from the repo root: `.env` is loaded relative to the current working directory.
- A MongoDB instance must be reachable at `MONGO_URI`; the lifespan pings it on startup and the app fails to start otherwise.
- There is no test suite, linter, formatter, typecheck, or CI configured. Verify changes by starting the server and exercising endpoints; `uv run python -c "import app.main"` catches import/config errors.

## Layout

- `app/main.py`: app creation and lifespan (Mongo connect/close).
- `app/api/v1/router.py`: mounts feature routers under `/v1`.
- Each feature (`auth`, `project`, `environment`, `variable`) is a package split into `routes.py` (HTTP + exception translation), `service.py` (business logic + Mongo access), `models.py` (stored documents), `schemas.py` (request/response), and `exceptions.py` (domain errors).
- Adding a new feature requires registering its router in `app/api/v1/router.py`.
- `app/core/`: `config.py` (pydantic-settings), `security.py` (password/JWT helpers), `dependencies.py` (`get_current_user_id` Bearer auth), `logger.py`, `utils.py`.
- `app/db/mongodb.py`: `mongo` singleton exposing `users`, `projects`, `environments`, and `variables` collections.

## Conventions and gotchas

- Services raise module-local exceptions; routes translate them to `HTTPException` and have a catch-all that logs and returns 500. Don't raise `HTTPException` from services.
- Cross-feature exceptions are imported directly (e.g. environment service raises `ProjectNotFound`/`UserNotFound`; variable service raises `EnvironmentNotFound`) instead of being redefined.
- Mongo documents use `_id: ObjectId`; Pydantic models alias it to `id` and serialize both `id` and datetimes to strings. Insert with `model_dump(by_alias=True, exclude_none=True)` and read with `model_validate`.
- Path IDs are converted with `ObjectId(...)` without validation, so a non-24-hex id raises `bson.errors.InvalidId` and surfaces as a 500.
- Collections are `None` until the lifespan connects; services guard with `if self.db.<collection> is None: raise RuntimeError(...)`. Query results use `.to_list(length=None)`.
- JWTs use `sub` as the user id; `JWT_EXPIRY` is in minutes. Project/environment endpoints enforce ownership, but variable endpoints only require a valid token and do not check project access.
- Project and environment `name` values must match `[a-z0-9_-]+`.
- `create_environemnt` is misspelled in both the service method and route function; keep call sites consistent if renaming it.
