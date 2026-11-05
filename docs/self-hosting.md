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
openssl rand -base64 32  # ENCRYPTION_KEY
```

> Put the generated values into `JWT_SECRET` and `ENCRYPTION_KEY` in `.env.docker`.

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
