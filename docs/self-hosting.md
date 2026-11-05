# Self-hosting sharenv-api

This guide deploys sharenv-api with Docker Compose, MongoDB, and nginx. nginx serves HTTP by default and switches to HTTPS automatically when you provide certificates.

## Requirements

- Docker Engine with the Compose plugin (`docker compose`)
- Compose v2.24 or newer for the external MongoDB override
- Ports 80 and 443 available (configurable)
- OpenSSL for generating secrets

## 1. Configure secrets

```bash
cp .env.docker.example .env.docker
chmod 600 .env.docker

openssl rand -hex 32     # JWT_SECRET
openssl rand -base64 32  # ENCRYPTION_KEY
```

Put the generated values into `JWT_SECRET` and `ENCRYPTION_KEY` in `.env.docker`.

`ENCRYPTION_KEY` encrypts stored variable values. Back it up separately and never commit `.env.docker` — losing this key makes the stored values unrecoverable.

## 2. Start with HTTP

```bash
docker compose up -d --build
docker compose ps
curl http://localhost/health
```

Expected response:

```json
{"status": "ok"}
```

Without certificates, nginx serves plain HTTP and logs `serving HTTP only`. Only expose this mode on a trusted network or behind another TLS-terminating proxy.

To use different host ports:

```bash
HTTP_PORT=8080 HTTPS_PORT=8443 docker compose up -d
```

The automatic HTTP-to-HTTPS redirect assumes HTTPS is published on 443.

## 3. Enable HTTPS with your own certificates

Place your certificate chain and private key here:

```
deploy/certs/fullchain.pem
deploy/certs/privkey.pem
```

- `fullchain.pem` should contain the leaf certificate followed by any intermediates.
- `privkey.pem` must be the matching private key.
- Restrict permissions: `chmod 600 deploy/certs/privkey.pem`.

Restart nginx so it detects the certificates:

```bash
docker compose restart nginx
docker compose logs nginx | grep nginx:
```

You should see `HTTPS enabled`. Then verify:

```bash
curl --cacert /path/to/your-ca.pem https://your-domain/health
curl -I http://your-domain
```

The HTTP request should return `301` with a redirect to HTTPS.

When renewing certificates, replace both files and restart nginx again. The filenames are fixed by `deploy/nginx/https.conf`.

## 4. Use an external MongoDB

By default, Compose starts a bundled `mongo:8.0` container with the `mongo_data` volume. To use your own MongoDB, edit `MONGO_URI` in `.env.docker`, then run:

```bash
docker compose -f compose.yaml -f compose.external-db.yaml up -d --build
```

This override disables the bundled MongoDB service and removes the API's dependency on it. Include credentials in the URI if your database requires authentication, for example:

```env
MONGO_URI=mongodb://user:password@db.example.com:27017/?authSource=admin
```

Percent-encode special characters in the username or password.

## 5. Operations

View logs:

```bash
docker compose logs -f api nginx
```

Update after pulling new code:

```bash
docker compose build --pull
docker compose up -d
```

Stop the stack while keeping data:

```bash
docker compose down
```

Delete the stack **and all data**:

```bash
docker compose down -v
```

Back up MongoDB:

```bash
docker compose exec -T mongo mongodump --archive --gzip > "sharenv-$(date +%F).archive.gz"
```

Restore:

```bash
docker compose exec -T mongo mongorestore --archive --gzip < sharenv-2026-01-01.archive.gz
```

Back up the `ENCRYPTION_KEY` from `.env.docker` separately. A database backup is useless without it.

## 6. Security notes

- MongoDB is not published to the host; only nginx is reachable.
- The API container runs as a non-root user with a read-only root filesystem and no Linux capabilities.
- Variable responses include `Cache-Control: no-store`.
- Keep `.env.docker` and `deploy/certs/privkey.pem` at mode `600`.
- The bundled MongoDB does not enable authentication because it is only reachable on the internal Compose network. Add authentication or use an external managed database if you need defense in depth.
- Always use `https://` for remote CLI access.

## 7. CLI configuration

The API contract is unchanged. The CLI only needs to:

- Use an `https://` base URL.
- Trust your CA when using a self-signed or private certificate (for example `--ca-cert` or `SHARENV_CA_BUNDLE`).
- Keep sending variable values as plain JSON — encryption at rest is handled by the API, and TLS protects values in transit.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| nginx logs `serving HTTP only` | Both `deploy/certs/fullchain.pem` and `privkey.pem` must exist and be readable |
| `502 Bad Gateway` | `docker compose logs api`; the API must be healthy before nginx starts |
| `ENCRYPTION_KEY must decode to 32 bytes` | Regenerate with `openssl rand -base64 32` |
| API cannot reach MongoDB | `MONGO_URI` must use `mongo` for the bundled service or your external hostname |
| HTTPS redirect goes to the wrong port | Publish HTTPS on 443 or edit the redirect in `deploy/nginx/https.conf` |
