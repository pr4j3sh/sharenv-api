# Self-hosting sharenv-api

This guide deploys sharenv-api with Docker Compose, MongoDB, and nginx.

> nginx serves HTTP by default and switches to HTTPS automatically when provided with certificates.

## Ways to run it

| # | How | Install steps | When to pick it |
|---|-----|---------------|-----------------|
| A | **Published image** + Compose | [Option A](#option-a-published-image--compose-recommended) | recommended; production |
| B | **Published image** + plain `docker run` | [Option B](#option-b-published-image-plain-docker-run) | you have an existing MongoDB and your own TLS terminator |
| C | **Build from source** + Compose | [Option C](#option-c-build-from-source-compose) | you want to audit/modify the code |
| D | **From source**, no container runtime | see [docs/development.md](development.md) | development |

The published images are multi-arch (`linux/amd64`, `linux/arm64`) and available at `docker.io/<DOCKER_USERNAME>/sharenv-api` with tags `X.Y.Z`, `X.Y` and `latest`. **Pin a version in production**; `latest` is for convenience. No GitHub Release page is published — tags are the only version signal; the image is the artifact.

## Requirements

- Docker Engine with the Compose plugin (`docker compose`)
- A MongoDB instance reachable by the API
- Ports 80 and 443 available (configurable)
- OpenSSL for generating secrets

## Option A — Published image + Compose (recommended)

```bash
git clone https://github.com/pr4j3sh/sharenv-api.git
cd sharenv-api
```

1. **Point the API at the released image.** Edit `compose.yaml`: replace the `build:` line in the `api` service with `image:` (nothing else changes):

   ```yaml
   services:
     api:
       image: <DOCKER_USERNAME>/sharenv-api:0.2.0
       restart: unless-stopped
       env_file: .env.docker
       expose:
         - "8000"
   ```

   Optional sanity check: `docker pull <DOCKER_USERNAME>/sharenv-api:0.2.0`

2. **Configure secrets** — see [Configure secrets](#configure-secrets).
3. **Point at your MongoDB** — see [Setup MongoDB](#setup-mongodb).
4. **Start it**:

   ```bash
   docker compose up -d
   curl http://localhost/health
   ```

   No `--build` flag needed. Then continue with [HTTPS](#enable-https-on-your-server) if you need it.

## Option B — Published image, plain `docker run`

For deployments where you run an external MongoDB and your own TLS terminator (nginx, Traefik, Caddy…) instead of the bundled compose stack:

```bash
docker run -d --name sharenv-api \
  -e MONGO_URI=mongodb://user:password@db.example.com:27017/?authSource=admin \
  -e JWT_SECRET=<openssl rand -hex 32> \
  -e ENCRYPTION_KEYS_FILE=/run/secrets/encryption_keys \
  -e ENCRYPTION_KEY_VERSION=1 \
  -v "$PWD/deploy/secrets:/run/secrets:ro" \
  -p 127.0.0.1:8000:8000 \
  <DOCKER_USERNAME>/sharenv-api:0.2.0
```

You supply the TLS certificate, the reverse proxy, and the database; the image itself is just the API.

## Option C — Build from source (Compose)

Identical to Option A, except keep `build: .` in `compose.yaml` as-is and start with:

```bash
docker compose up -d --build
```

## Option D — From source, no containers

Development setup with `uv` and Python 3.15+; see [docs/development.md](development.md).

## Configure secrets

- Copy `.env.docker.example` to `.env.docker`:

  ```bash
  cp .env.docker.example .env.docker
  ```

- Generate `JWT` secret:

  ```bash
  openssl rand -hex 32     # JWT_SECRET
  ```

  > Put the JWT value into `JWT_SECRET` in `.env.docker`.

- Create the master key registry, a JSON object mapping key versions to keys.

  > Compose mounts it into the API container as a Docker secret, so the master key never appears in `.env.docker` or in `docker inspect` output:

  ```bash
  mkdir -p deploy/secrets
  umask 077
  printf '{"1": "%s"}\n' "$(openssl rand -base64 32)" > deploy/secrets/encryption_keys.json
  ```

  > `ENCRYPTION_KEYS_FILE` in `.env.docker` already points at the in-container path `/run/secrets/encryption_keys`, and `ENCRYPTION_KEY_VERSION=1` marks that key active. Rotating the master key is documented in [docs/key-rotation.md](key-rotation.md).

### Email (optional but recommended)

sharenv does **not** require a mail server to function. By default
(`EMAIL_PROVIDER=none`) no mail is sent: accounts are created unverified,
unverified users **can log in**, and invitation tokens are returned by the
API so the owner can share them out-of-band (Slack, in person, …). The
invitation response includes both `token` and `email_sent`.

> **Warning — `EMAIL_PROVIDER=none` weakens identity.** Without email, an
> account's address is self-asserted: anyone who can reach a publicly exposed
> instance can claim to be `alice@abc.com`. In this mode you **must** restrict
> network access (VPN, nginx allowlist, or an SSO proxy in front of the API),
> and treat `email_verified=false` in login/refresh responses as a signal, not
> as proof. The sharenv CLI warns on sensitive actions (invites, member
> changes, project delete, variable push/delete) while your account is
> unverified; the warning can be ignored only on a trusted network.

Three supported setups:

#### No mail (default)

```env
EMAIL_PROVIDER=none
```

#### Your organization's mail relay (recommended when available)

```env
EMAIL_PROVIDER=smtp
SMTP_HOST=mailrelay.abc.com     # or smtp-relay.gmail.com (Workspace)
SMTP_PORT=587
SMTP_USER=                      # empty for an IP/host allowlisted relay
SMTP_PASSWORD=
SMTP_TLS=starttls               # starttls | ssl | none
EMAIL_FROM=sharenv <sharenv@abc.com>
```

#### Resend

```env
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxxxxx
EMAIL_FROM=Acme <no-reply@abc.com>   # a sender verified in Resend
```

> To move from `none` to `smtp`/`resend` later, existing unverified users can
> verify through the usual resend-OTP flow — no migration needed.

> `DEBUG=True` and `EMAIL_PROVIDER=console` both skip delivery and log OTPs
> and invitation tokens; never enable them in production. `console` exists for
> local development only. The app refuses to start with
> `EMAIL_PROVIDER=console` unless `DEBUG=True`, so production can't silently
> log secrets.

### Optional tuning (defaults shown)

```env
DOCS_ENABLED=False          # API docs (/docs, /redoc, /openapi.json)
JWT_EXPIRY=15               # access token lifetime in minutes
REFRESH_TOKEN_EXPIRY_DAYS=30
OTP_EXPIRY=10               # minutes before a verification OTP expires
OTP_LENGTH=6                # digits in the OTP
AUTH_RATE_LIMIT_PER_IP=30   # requests/min across /v1/auth/*
LOGIN_FAILURE_LIMIT=5       # failed logins per email before lockout
LOGIN_LOCKOUT_MINUTES=15
OTP_VERIFY_ATTEMPTS=10      # wrong OTP guesses per email per OTP lifetime
OTP_RESEND_LIMIT=3          # OTP resends per email per OTP lifetime
INVITATION_EXPIRY_DAYS=7    # days before a pending project invitation expires
```

> Never enable `DEBUG` in production: it disables email delivery and logs
> verification OTPs. Keep `DOCS_ENABLED` false in production unless you
> intentionally expose the API schema. The API enforces in-memory auth rate
> limits (single-process); nginx adds a coarse outer limit on `/v1/auth/`.

## Setup MongoDB

The bundled stack ships no database. Edit `MONGO_URI` in `.env.docker`
(point at your managed service or your own instance — Atlas,
DocumentDB-compatible, a separate container, a VM…). The API pings MongoDB
at startup and exits if it cannot reach it, so it won't serve before the
database is ready.

Include credentials in the URI if your database requires authentication, for example:

```env
MONGO_URI=mongodb://user:password@db.example.com:27017/?authSource=admin
```

## Setting up HTTP Server

- Start the stack:

  ```bash
  docker compose up -d
  docker compose ps
  curl http://localhost/health
  ```

  > Expected response: `{ "status": "ok", "checks": { "app": "ok" } }`

  > Without certificates, nginx serves plain HTTP and logs `serving HTTP only`. Only expose this mode on a trusted network or behind another TLS-terminating proxy.

- To use different host ports:

  ```bash
  HTTP_PORT=8080 HTTPS_PORT=8443 docker compose up -d
  ```

  > The automatic HTTP-to-HTTPS redirect assumes HTTPS is published on 443.

## Enable HTTPS on your server

- Place your certificate chain and private key here:

  ```
  deploy/certs/fullchain.pem
  deploy/certs/privkey.pem
  ```

- Restart nginx so it detects the certificates:

  ```bash
  docker compose restart nginx
  docker compose logs nginx | grep nginx:
  ```

- You should see `HTTPS enabled`. Then verify:

  ```bash
  curl --cacert /path/to/your-ca.pem https://your-domain/health
  curl -I http://your-domain
  ```

  > The HTTP request should return `301` with a redirect to HTTPS.

- When renewing certificates, replace both files and restart nginx again. The filenames are fixed by `deploy/nginx/https.conf`.
