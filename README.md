# sharenv-api

sharenv API server code for managing projects environment variables
and sharing them.

## Requirements

- Python 3.15+
- [uv](https://docs.astral.sh/uv/)
- MongoDB instance

## Installation

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
openssl rand -base64 32  # ENCRYPTION_KEY
```

Paste the generated values into `JWT_SECRET` and `ENCRYPTION_KEY` in `.env`.

`ENCRYPTION_KEY` encrypts variable values at rest with AES-256-GCM. Back it up separately — losing it means losing all stored values.

## Usage

Run from the repository root so `.env` is loaded from the current working directory:

```bash
uv run fastapi dev
```

The server starts on `http://127.0.0.1:8000`.

- Interactive docs: <http://127.0.0.1:8000/docs>
- Health check: `GET /health` → `{"status": "ok"}`

The API refuses to start if MongoDB is unreachable.

## Production

The dev server speaks plain HTTP. Always run the API behind TLS in production — use a Caddy/Nginx reverse proxy, or Uvicorn with `--ssl-certfile` and `--ssl-keyfile` — and point the CLI at an `https://` base URL so tokens and variable values are encrypted in transit. Variable responses send `Cache-Control: no-store`.

## Self-hosting

A Docker Compose deployment with nginx, HTTP/HTTPS support, and bundled or external MongoDB is documented in [docs/self-hosting.md](docs/self-hosting.md).

Quick start:

```bash
cp .env.docker.example .env.docker
# set JWT_SECRET and ENCRYPTION_KEY in .env.docker
docker compose up -d --build
```
