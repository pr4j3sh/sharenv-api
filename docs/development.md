# Running from source

Local setup for development or running the API without Docker. For production
deployment with Docker Compose, see [self-hosting.md](self-hosting.md).

## Requirements

- [Python 3.15+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/)
- A MongoDB instance reachable at `MONGO_URI` (the lifespan pings it on
  startup; startup fails without it)

## Setup

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
> `ENCRYPTION_KEY_VERSION` is the active key version; rotation is documented
> in [key-rotation.md](key-rotation.md).

- run the API (from the repository root so `.env` is loaded from the current
  working directory):

```bash
uv run fastapi dev
```

> The server starts on `http://127.0.0.1:8000`. If `DOCS_ENABLED` is `True`,
> API docs are at <http://127.0.0.1:8000/docs> (disabled by default in
> production/Docker configs).
