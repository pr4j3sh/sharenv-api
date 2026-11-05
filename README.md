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
openssl rand -hex 32
```

Paste the generated value into `JWT_SECRET` in `.env`.

## Usage

Run from the repository root so `.env` is loaded from the current working directory:

```bash
uv run fastapi dev
```

The server starts on `http://127.0.0.1:8000`.

- Interactive docs: <http://127.0.0.1:8000/docs>
- Health check: `GET /health` → `{"status": "ok"}`

The API refuses to start if MongoDB is unreachable.
