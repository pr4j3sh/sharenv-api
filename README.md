# sharenv-api

A self-hosted API server for securely managing, syncing, and sharing project environment variables. Provides centralized storage and access management for environment configurations.

Use [`pr4j3sh/sharenv`](https://github.com/pr4j3sh/sharenv) `CLI` client along with this.

## Requirements

- [Python 3.15+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/)
- [MongoDB](https://www.mongodb.com/) (Optional)

## Self-hosting

### Using Docker

Follow instructions at [docs/self-hosting.md](docs/self-hosting.md).

### Using Source

- clone repository

```bash
git clone https://github.com/pr4j3sh/sharenv-api
cd sharenv-api
```

- install dependencies

```bash
uv sync
```

- setup environment variables

```bash
cp .env.example .env
openssl rand -hex 32     # JWT_SECRET
openssl rand -base64 32  # master key
```

> Paste the JWT value into `JWT_SECRET` in `.env`, and the master key into
> `ENCRYPTION_KEYS_JSON` as version 1, e.g.
> `ENCRYPTION_KEYS_JSON={"1": "<base64 key>"}`. Also add `MONGO_URI`.
> `ENCRYPTION_KEY_VERSION` is the active key version; rotation is documented in
> [docs/key-rotation.md](docs/key-rotation.md).

- Run from the repository root so `.env` is loaded from the current working directory:

```bash
uv run fastapi dev
```

> The server starts on `http://127.0.0.1:8000`. Browse API docs at <http://127.0.0.1:8000/docs>

## Security

Values are encrypted server-side, not end-to-end: the API decrypts them before
returning them, so a compromised server or operator can read every value. Read
the trust model and data classification in [docs/security.md](docs/security.md)
before storing real production secrets.

New routes and services must pass
[docs/security-review.md](docs/security-review.md).

## Next Steps

- [Install sharenv CLI](https://github.com/pr4j3sh/sharenv)
