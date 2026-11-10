# Self-hosting sharenv-api

This guide deploys sharenv-api with Docker Compose, MongoDB, and nginx. nginx serves HTTP by default and switches to HTTPS automatically when provided with certificates.

## Requirements

- Docker Engine with the Compose plugin (`docker compose`)
- Compose v2.24 or newer for the external MongoDB override
- Ports 80 and 443 available (configurable)
- OpenSSL for generating secrets

## 1. Configure secrets

```bash
cp .env.docker.example .env.docker
openssl rand -hex 32     # JWT_SECRET
openssl rand -base64 32  # master key
```

> Put the JWT value into `JWT_SECRET` in `.env.docker`.

Create the master key registry — a JSON object mapping key versions to keys.
Compose mounts it into the API container as a Docker secret, so the master key
never appears in `.env.docker` or in `docker inspect` output:

```bash
mkdir -p deploy/secrets
umask 077
printf '{"1": "%s"}\n' "$(openssl rand -base64 32)" > deploy/secrets/encryption_keys.json
```

> `deploy/secrets/` is gitignored. `ENCRYPTION_KEYS_FILE` in `.env.docker`
> already points at the in-container path `/run/secrets/encryption_keys`, and
> `ENCRYPTION_KEY_VERSION=1` marks that key active. Rotating the master key is
> documented in [docs/key-rotation.md](key-rotation.md).

## Email (optional but recommended)

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

### A. No mail (default) — out-of-band invites

```env
EMAIL_PROVIDER=none
```

Workflow: create the project → `sharenv invite create` → share the printed
token with the teammate → teammate runs `sharenv invite accept <token>`.
No DNS, SPF, or third-party account needed. Note that unverified accounts
cannot complete OTP verification, so login simply does not require it in this
mode; `email_verified` in the login/refresh response is always `false`.

### B. Your org's mail relay (recommended when available)

```env
EMAIL_PROVIDER=smtp
SMTP_HOST=mailrelay.abc.com     # or smtp-relay.gmail.com (Workspace)
SMTP_PORT=587
SMTP_USER=                      # empty for an IP/host allowlisted relay
SMTP_PASSWORD=
SMTP_TLS=starttls               # starttls | ssl | none
EMAIL_FROM=sharenv <sharenv@abc.com>
```

Works with: an internal Postfix relay, Google Workspace SMTP relay
(`smtp-relay.gmail.com`, registered IPs or SMTP AUTH with a service mailbox),
Microsoft 365 (`smtp.office365.com:587` — enable *Authenticated SMTP* for a
service mailbox; basic-auth SMTP is being deprecated), or the SMTP endpoint of
any transactional provider (SES, SendGrid, Mailgun…). Intra-org delivery
through your own relay needs no SPF/DKIM/DMARC work.

With a provider configured, OTP verification is enforced as usual, invitation
emails are sent, and the invitation token is *also* returned in the API
response as a fallback. Email delivery is best-effort: an SMTP outage does not
block invites (`email_sent: false` in the response tells you to share the
token yourself).

### C. Resend

```env
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxxxxx
EMAIL_FROM=Acme <no-reply@abc.com>   # a sender verified in Resend
```

Same behavior as (B); needs a Resend account and a verified domain/sender.

To move from `none` to `smtp`/`resend` later, existing unverified users can
verify through the usual resend-OTP flow — no migration needed.

> `DEBUG=True` and `EMAIL_PROVIDER=console` both skip delivery and log OTPs
> and invitation tokens; never enable them in production. `console` exists for
> local development only.

Optional tuning (defaults shown):

```env
DOCS_ENABLED=False          # API docs (/docs, /redoc, /openapi.json)
JWT_EXPIRY=15               # access token lifetime in minutes
REFRESH_TOKEN_EXPIRY_DAYS=30
OTP_EXPIRY=10               # minutes before a verification OTP expires
OTP_LENGTH=6                # digits in the OTP
AUTH_RATE_LIMIT_PER_IP=30   # requests/min across /v1/auth/*
LOGIN_FAILURE_LIMIT=5       # failed logins per email before lockout
LOGIN_LOCKOUT_MINUTES=15
OTP_VERIFY_ATTEMPTS=10      # wrong OTP guesses per user per OTP lifetime
OTP_RESEND_LIMIT=3          # OTP resends per user per OTP lifetime
INVITATION_EXPIRY_DAYS=7    # days before a pending project invitation expires
```

> Never enable `DEBUG` in production: it disables email delivery and logs
> verification OTPs. Keep `DOCS_ENABLED` false in production unless you
> intentionally expose the API schema. The API enforces in-memory auth rate
> limits (single-process); nginx adds a coarse outer limit on `/v1/auth/`.

## 2. Start with HTTP

```bash
docker compose up -d --build
docker compose ps
curl http://localhost/health
```

Expected response:

```json
{ "status": "ok" }
```

> Without certificates, nginx serves plain HTTP and logs `serving HTTP only`. Only expose this mode on a trusted network or behind another TLS-terminating proxy.

- To use different host ports:

```bash
HTTP_PORT=8080 HTTPS_PORT=8443 docker compose up -d
```

> The automatic HTTP-to-HTTPS redirect assumes HTTPS is published on 443.

## 3. Enable HTTPS with your own certificates

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

## 4. Use an external MongoDB

- By default, Compose starts a bundled `mongo:8.0` container with the `mongo_data` volume. To use your own MongoDB, edit `MONGO_URI` in `.env.docker`, then run:

```bash
docker compose -f compose.yaml -f compose.external-db.yaml up -d --build
```

- This override disables the bundled MongoDB service and removes the API's dependency on it. Include credentials in the URI if your database requires authentication, for example:

```env
MONGO_URI=mongodb://user:password@db.example.com:27017/?authSource=admin
```
