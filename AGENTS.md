# AGENTS.md

FastAPI + async MongoDB (PyMongo `AsyncMongoClient`) API for managing projects, environments, and variables. Python 3.15, managed with `uv`.

## Setup and commands

- `cp .env.example .env`, then set `JWT_SECRET` (`openssl rand -hex 32`) and a master key registry: `ENCRYPTION_KEYS_JSON={"1": "<openssl rand -base64 32>"}` (or `ENCRYPTION_KEYS_FILE` pointing at a JSON file). `ENCRYPTION_KEY_VERSION` is the active version. `settings` validates the registry at import time, so bad values break every command, not just server startup.
- `uv sync` installs deps; `uv add <pkg>` updates `pyproject.toml` and `uv.lock`.
- Run `uv run fastapi dev` from the repo root (`.env` is loaded relative to the current working directory); docs at `/docs`, health at `/health`.
- A MongoDB instance must be reachable at `MONGO_URI`; the lifespan pings it and startup fails otherwise.
- There is no test suite, linter, formatter, typecheck, or CI configured. Verify by starting the server and exercising endpoints; `uv run python -c "import app.main"` catches import/config errors.

## Layout

- `app/main.py`: app creation, lifespan, `/health`, and middleware that adds `Cache-Control: no-store` to `/v1/variable*` responses. API docs (`/docs`, `/redoc`, `/openapi.json`) are enabled only when `DOCS_ENABLED` is true.
- `app/api/v1/router.py`: mounts feature routers under `/v1`. Adding a feature requires registering its router here.
- Each feature (`auth`, `project`, `environment`, `variable`, `invitation`) is a package split into `routes.py` (HTTP + exception translation), `service.py` (business logic + Mongo access), `models.py` (stored documents), `schemas.py` (request/response), and `exceptions.py` (domain errors).
- `app/core/`: `config.py` (pydantic-settings), `security.py` (password/JWT helpers + token claims), `crypto.py` (AES-GCM value encryption), `dependencies.py` (`get_current_user_id` Bearer auth with per-request user/version checks), `rate_limit.py` (in-memory auth rate limiting), `logger.py`, `utils.py`.
- `app/db/mongodb.py`: `mongo` singleton exposing `users`, `projects`, `environments`, `variables`, and `invitations` collections.

## Conventions and gotchas

- Services raise module-local exceptions; routes translate them to `HTTPException` and have a catch-all that logs and returns 500. Don't raise `HTTPException` from services.
- Cross-feature exceptions are imported directly (environment raises `ProjectNotFound`/`UserNotFound`; variable raises `EnvironmentNotFound`; environment raises `DeleteVariableFailed`) instead of being redefined.
- Status-code mapping is normalized: `401` is for missing/invalid/expired bearer authentication only; `404` is for not-found-or-not-a-member (private resources are hidden); `403` is for an authenticated member who is authenticated but forbidden (e.g. reader attempting a write). Keep new routes aligned with this policy.
- Access model: `projects.user_id` is the owner. `projects.members` holds `{user_id, role, environments}` entries where `role` is `writer` or `reader` and `environments` is an explicit list of granted environment ids (no wildcard; owner has implicit access to all envs). `app/api/v1/project/permissions.py` resolves access.
  - Roles (uniform RBAC): `owner` — full control. `writer` — read granted envs/vars and create/update/delete vars in granted envs, create/delete envs (env access is still grant-gated; writer-created envs are not auto-granted). `reader` — read-only on granted envs/vars. Only the owner can invite, change member access, remove members, or delete the project.
  - Sharing is by invitation (consent required), not direct add: `POST /v1/project/{project_id}/invitations` (owner, re-auth; body `email, role, environments, password`), `GET/DELETE /v1/project/{project_id}/invitations[/{invitation_id}]` (owner), `POST /v1/invitations/{token}/accept` (authenticated+verified user whose email matches). Invitation tokens are random and stored hashed with expiry (`INVITATION_EXPIRY_DAYS`); `DEBUG` logs the token. `PUT /v1/project/{id}` no longer adds members.
  - Member management (owner, re-auth where noted): `PATCH /v1/project/{project_id}/members/{user_id}` replaces granted envs/role (`{environments, role?, password}`), `DELETE /v1/project/{project_id}/members/{user_id}` removes a member (`{password}`), `DELETE /v1/project/{project_id}/members/me` lets a member leave. Access is enforced from DB membership/grants on each request, so removal/grant changes take effect immediately.
  - Project deletion (`DELETE /v1/project/{id}`, `/v1/project/name/{project_name}`) requires the caller's current password (re-auth). Variables/environments resolve their project and enforce role + env grant. No membership migration script is provided (the DB is treated as temporary).
- Mongo documents use `_id: ObjectId`; Pydantic models alias it to `id` and serialize `id` and datetimes to strings. Insert with `model_dump(by_alias=True, exclude_none=True)` and read with `model_validate`. `UserModel` stores auth state (email, Argon2 password, verification/OTP fields, `token_version`, `refresh_jti`) rather than an `_id`/timestamps-shaped record.
- Path IDs are converted with `ObjectId(...)` without validation, so a non-24-hex id raises `bson.errors.InvalidId` and surfaces as a 500.
- Variable values are never stored in plaintext: `value_enc` is AES-GCM encrypted with the project's data key and an AAD of `[project_id, environment_id, name, key_version]` (JSON array). Each value and each project's wrapped key record their `key_version`, which must stay present in the master key registry. Changing a variable's `name`/`environment_id`/project, or removing its key version from the registry, without re-encrypting makes it undecryptable. Rotate master keys with `uv run python -m scripts.rotate_keys` (runbook: `docs/key-rotation.md`).
- Collections are `None` until the lifespan connects; services guard with `if self.db.<collection> is None: raise RuntimeError(...)`. List endpoints (projects, environments, variables) use bounded `skip`/`limit` queries and expose `X-Total-Count`, `X-Limit`, `X-Offset`, and optional `X-Next-Offset` headers rather than `.to_list(length=None)`.
- Auth: `POST /v1/auth/login` and verify return `{token, refresh_token}` (access tokens carry `sub`, `iat`, `exp`, `jti`, `ver`, `typ:"access"`; refresh tokens are `typ:"refresh"`, single-use, rotated via `POST /v1/auth/refresh`). `JWT_EXPIRY` is in minutes (default 15); `REFRESH_TOKEN_EXPIRY_DAYS` defaults to 30. `POST /v1/auth/logout` bumps `users.token_version` (revoking all issued tokens). `get_current_user_id` validates the token, checks the user exists, and enforces `ver` on every request. Login never returns 404: unknown email and wrong password are identical `401`; unverified with correct password is `403 email_not_verified`. Emails are trimmed and lowercased on register and login.
- Auth rate limiting: in-memory, single-process counters in `app/core/rate_limit.py` (per-IP across `/v1/auth/*`, per-email login lockout, OTP verify/resend throttles) with nginx `limit_req` for `/v1/auth/` in `deploy/nginx/`. Config knobs: `AUTH_RATE_LIMIT_PER_IP`, `LOGIN_FAILURE_LIMIT`, `LOGIN_LOCKOUT_MINUTES`, `OTP_VERIFY_ATTEMPTS`, `OTP_RESEND_LIMIT`.
- Project and environment `name` values must match `[a-z0-9_-]+`.
- Misspellings are load-bearing: `create_environemnt` (service and route) and `delete_environemnt` (route). Keep call sites consistent if renaming.
- Security-sensitive changes must satisfy `docs/security-review.md`; the trust model and data classification are in `docs/security.md`. Values are decrypted server-side, so never claim end-to-end encryption.

## Deployment

- `docs/self-hosting.md` is the deployment guide. Compose reads `.env.docker` (not `.env`) and runs the API, a bundled `mongo:8.0`, and nginx.
- `docker compose up -d --build`; for an external DB use `docker compose -f compose.yaml -f compose.external-db.yaml up -d --build`.
- nginx picks HTTP or HTTPS at container start based on whether `deploy/certs/fullchain.pem` and `privkey.pem` exist (`deploy/nginx/40-select-config.sh`); those filenames are fixed.
- The runtime image runs non-root with a read-only root filesystem and a `/tmp` tmpfs; write only to `/tmp`. It starts `uvicorn app.main:app` without reload.
