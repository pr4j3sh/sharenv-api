# Self-hosting sharenv-api

This guide deploys sharenv-api with Docker Compose, MongoDB, and nginx.

> nginx serves HTTP by default and switches to HTTPS automatically when provided with certificates.

## Install from the released image

The recommended way to run sharenv-api is the published container image — you don't build from source. Every `vX.Y.Z` tag publishes a multi-arch (amd64 + arm64) image to Docker Hub at `docker.io/<DOCKER_USERNAME>/sharenv-api:<version>`, and a GitHub release page (with auto-generated notes and a source tarball) is created for the same tag at `https://github.com/pr4j3sh/sharenv-api/releases`.

`latest` tracks the newest tag, but **pin a version in production** — `latest` is for convenience.

The image contains only the API: no database and no nginx inside it. The compose stack (nginx + your MongoDB) ships separately — clone the repo to get it:

```bash
git clone https://github.com/pr4j3sh/sharenv-api.git
cd sharenv-api
```

### 1. Point the API at the released image

Edit `compose.yaml`: replace the `build:` line in the `api` service with `image:` (that is the only difference from the from-source install):

```yaml
services:
  api:
    image: <DOCKER_USERNAME>/sharenv-api:0.2.0
    restart: unless-stopped
    env_file: .env.docker
    expose:
      - "8000"
```

Optional sanity check:

```bash
docker pull <DOCKER_USERNAME>/sharenv-api:0.2.0
```

### 2. Configure secrets

Exactly as the from-source flow — copy `.env.docker.example` to `.env.docker`, set `JWT_SECRET` (`openssl rand -hex 32`), and create the master key registry at `deploy/secrets/encryption_keys.json` (see [Configure secrets](#configure-secrets)). The released image reads `/run/secrets/encryption_keys` the same as a locally built one.

### 3. Point at your MongoDB

The bundled stack ships no database. Edit `MONGO_URI` in `.env.docker` to your instance — managed service (Atlas, DocumentDB-compatible) or your own — see [Setup MongoDB](#setup-mongodb).

### 4. Start it

```bash
docker compose up -d
curl http://localhost/health
```

No `--build` flag needed. Then continue with [HTTP](#setting-up-http-server) and [HTTPS](#enable-https-on-your-server) as usual, or see [Setup MongoDB](#setup-mongodb).

### Without Docker Compose

```bash
docker run -d --name sharenv-api \
  -e MONGO_URI=mongodb://user:password@db.example.com:27017/?authSource=admin \
  -e JWT_SECRET=<openssl rand -hex 32> \
  -e ENCRYPTION_KEYS_FILE=/run/secrets/encryption_keys \
  -e ENCRYPTION_KEY_VERSION=1 \
  -v $PWD/deploy/secrets:/run/secrets:ro \
  -p 127.0.0.1:8000:8000 \
  <DOCKER_USERNAME>/sharenv-api:0.2.0
```

You then provide your own TLS terminator (nginx, Traefik, Caddy…) in front; there is no bundled nginx in this mode.

## Requirements

- Docker Engine with the Compose plugin (`docker compose`)
- A MongoDB instance reachable by the API
- Ports 80 and 443 available (configurable)
- OpenSSL for generating secrets

## Configure secrets

- Copy the `.env.docker.example` file as `.env.docker`

```bash
cp .env.docker.example .env.docker
```

- Generate `JWT` secret

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

> `ENCRYPTION_KEYS_FILE` in `.env.docker`
> already points at the in-container path `/run/secrets/encryption_keys`, and
> `ENCRYPTION_KEY_VERSION=1` marks that key active. Rotating the master key is
> documented in [docs/key-rotation.md](key-rotation.md).

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

## Setting up HTTP Server

- Build and run docker container

```bash
docker compose up -d --build
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

## Setup MongoDB

Edit `MONGO_URI` in `.env.docker` to the mongodb instance.

Include credentials in the URI if your database requires authentication, for example:

```env
MONGO_URI=mongodb://user:password@db.example.com:27017/?authSource=admin
```
