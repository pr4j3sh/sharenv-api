# sharenv-api

sharenv API server codebase

- create a random secret

```bash
openssl rand -hex 32
```

- add secret to `.env.example` and rename file to `.env`

```bash
mv .env.example .env
```

- run app

```bash
uv run fastapi dev
```
