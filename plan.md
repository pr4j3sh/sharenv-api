# sharenv-api — security remediation plan

Companion plan for the CLI lives at `../sharenv/plan.md`.

This plan is ordered by risk. Work top-to-bottom where possible. Each task is a
single reviewable change. `P0` = do before storing real production secrets,
`P1` = important hardening, `P2` = polish.

Legend: `- [ ]` todo, `- [x]` done. Add the PR/commit next to a task when you
finish it.

---

## 1. Trust model and architecture

Decide and document what the server is allowed to see before changing crypto.

- [x] **P0 — Write the threat model.** Add `docs/security.md` covering: what the
      server can read, what a DB-only attacker gets, what a stolen token gets,
      what a malicious project member gets, and what a compromised host gets.
      Acceptance: the doc explicitly states that values are decrypted server-side.
      (`docs/security.md`)
- [x] **P0 — Decide server-side vs end-to-end encryption.** If the server must
      never see plaintext, move encryption into the CLI (per-project key) and
      make the API store opaque blobs. If server-side stays, state that server
      compromise = all secrets. (`docs/security.md` — server-side, documented)
- [x] **P1 — Define data classification.** Values are secret; names/metadata are
      currently plaintext. Decide whether variable names and project names are
      also sensitive, and document it. (`docs/security.md` — sensitive metadata)
- [x] **P1 — Add a security review checklist** for future routes: auth required,
      membership checked, input validated, response filtered, no secrets logged.
      (`docs/security-review.md`)

---

## 2. Cryptography and key management

Current code: `app/core/crypto.py`, `app/api/v1/variable/service.py`,
`app/api/v1/variable/models.py`, `app/core/config.py`.

- [x] **P0 — Add per-project (or per-tenant) data keys.** Generate a random
      32-byte data key per project, encrypt it with a master key, store the
      wrapped key on the project document. Encrypt variable values with the
      project data key. Acceptance: a leaked single project key cannot decrypt
      another project.
- [x] **P0 — Implement a real key-version registry.** Replace the single
      module-global `_key` with a map `{version: AESGCM}` loaded from config.
      `encrypt_value` writes the active version; `decrypt_value` takes
      `key_version` and selects the right key. Acceptance: old values remain
      readable after rotating `ENCRYPTION_KEY`.
      (registry in `app/core/config.py` — `ENCRYPTION_KEYS_JSON`/`ENCRYPTION_KEYS_FILE`)
- [x] **P0 — Add a re-encryption/migration command.** A script or management
      endpoint that walks variables and re-encrypts with the active key version.
      Acceptance: documented runbook for rotation; idempotent; resumable.
      (`scripts/rotate_keys.py`, `docs/key-rotation.md`)
- [x] **P0 — Bind key version into the AAD.** Change `_aad` to include
      `key_version` (and ideally `project_id`) so a ciphertext cannot be
      re-labelled with a different version/project. Plan a migration because
      this changes existing ciphertext.
      (`app/core/crypto.py` — AAD is a JSON array of `[project_id, environment_id, name, key_version]`)
- [x] **P0 — Store the master key outside the repo/host config.** Use Docker
      secrets or an external KMS. Do not put `ENCRYPTION_KEY` in `.env` next to
      `MONGO_URI`. Acceptance: `docker inspect` does not expose the key.
      (compose `secrets:` → `/run/secrets/encryption_keys`; `JWT_SECRET` still §9)
- [x] **P1 — Add per-variable error isolation.** `get_variables` should skip or
      report a single undecryptable variable instead of failing the whole
      environment (`variable/service.py:138-151`). Return a structured error or
      an `undecryptable` flag.
- [x] **P1 — Define crypto-shredding.** Decide whether deleting a project
      destroys its wrapped data key. Document that Mongo backups/oplog may still
      contain ciphertext.
      (`docs/security.md` — Crypto-shredding section)
- [ ] **P1 — Add crypto tests.** Nonce uniqueness, tamper detection (flip a
      ciphertext byte), AAD mismatch (wrong name/env), wrong key version,
      rotation round-trip.

---

## 3. Authentication and token lifecycle

Current code: `app/api/v1/auth/*`, `app/core/security.py`,
`app/core/dependencies.py`, `app/core/config.py`.

- [x] **P0 — Add email verification.** Registration should create an unverified
      user and send a verification token; login/secret access must be blocked
      until verified. Acceptance: an attacker cannot register a victim's email
      and receive a usable token.
- [x] **P0 — Add a password policy.** Minimum length (>= 12), maximum length
      (e.g. 1024 bytes) to avoid Argon2 DoS, and reject obvious weak/breached
      passwords. Validate in `RegisterReq`/`LoginReq` (`auth/schemas.py`).
- [x] **P0 — Add rate limiting and lockout.** Per-IP and per-email limits on
      `/v1/auth/register` and `/v1/auth/login`. Prefer nginx `limit_req` plus an
      app-level counter. Acceptance: brute-force and password-spray tests are
      throttled.
      (in-memory counters in `app/core/rate_limit.py`, also throttles OTP
      verify/resend; nginx `limit_req` for `/v1/auth/` in `deploy/nginx/`)
- [ ] **P1 — Add MFA/TOTP for accounts.** Optional at first, required for
      project owners. Document recovery codes.
- [x] **P0 — Stop leaking account existence.** Return the same `401` body and
      timing for unknown email and wrong password (`auth/routes.py:48-74`,
      `auth/service.py:48-66`). Use a dummy hash when the user is missing.
      Remove the `404 UserNotFound` path. Also fix `add_user` returning `401
UserNotFound` for an unknown email (`project/routes.py:82-107`).
      (login returns identical 401 for unknown/wrong; `add_user` returns 404
      for unknown target email)
- [x] **P0 — Enforce a strong `JWT_SECRET`.** Reject secrets shorter than 32
      bytes / low entropy in `Settings.validate_jwt_secret`
      (`core/config.py:25-30`). Acceptance: startup fails for `secret`.
- [x] **P0 — Allowlist the JWT algorithm.** Reject anything except
      `HS256/HS384/HS512` in config validation; never allow `none`.
- [x] **P0 — Add token revocation/logout.** Add `jti` to tokens and a
      revocation list (or per-user `token_version`) checked in
      `get_current_user_id`. Add `POST /v1/auth/logout`.
      (`jti`/`ver`/`typ` claims, `users.token_version`, `POST /v1/auth/logout`)
- [x] **P1 — Add refresh tokens or a shorter access token.** Keep access tokens
      short (e.g. 15 min) and add refresh rotation. Update the CLI accordingly.
      (`JWT_EXPIRY` 15 min, `POST /v1/auth/refresh`, single-use rotated refresh
      tokens; replay revokes the chain)
- [x] **P1 — Add re-authentication for sensitive actions.** Require the current
      password (or a fresh token) for `PUT /project/{id}` (share), project
      deletion, and future member removal.
      (password required on `PUT /v1/project/{id}` and project delete by id/name)
- [x] **P1 — Verify the user still exists on every request.** Check `users`
      (or cache) in `get_current_user_id`, not only inside individual services.
      Acceptance: deleting a user invalidates access immediately.
- [x] **P2 — Disable `/docs` and `/openapi.json` in production** (or protect
      them). Gate on `DEBUG` or a separate setting in `app.main.py`.
      (`DOCS_ENABLED`, default false)
- [x] **P2 — Make missing/invalid tokens consistently return `401` with
      `WWW-Authenticate: Bearer`.** `HTTPBearer` may return `403` for a missing
      header; normalize it.
      (verified: missing and invalid bearer tokens return `401` with
      `WWW-Authenticate: Bearer`)

---

## 4. Sharing, authorization, and roles

Current code: `app/api/v1/project/*`, `app/api/v1/environment/*`,
`app/api/v1/variable/*`.

- [x] **P0 — Require consent for project membership.** Change `add_user` to
      create a pending invitation; the invited user must accept before gaining
      access (`project/service.py:67-104`). Notify the invitee. Acceptance: an
      owner cannot silently grant access.
      (`POST /v1/project/{project_id}/invitations`, `POST /v1/invitations/{token}/accept`;
      token emailed, hashed at rest with expiry; accept requires matching verified user)
- [x] **P0 — Add roles.** At minimum `owner`, `writer`, `reader`. Store roles on
      the project (`users` becomes `members: [{user_id, role}]`). Readers must
      not update/delete variables or delete environments.
      (`members: [{user_id, role, environments}]`, uniform RBAC via `project/permissions.py`)
- [x] **P0 — Add member removal and "leave project".** `DELETE
/project/{id}/members/{user_id}` (owner only) and `DELETE
/project/{id}/members/me`. Acceptance: revoked users lose access
      immediately; combine with token version/revocation if needed.
      (plus `PATCH /v1/project/{project_id}/members/{user_id}` to update env grants/role;
      enforced from DB on every request)
- [x] **P0 — Scope permissions per environment.** Decide whether prod is
      owner-only or role-gated. Enforce in `_get_environment_for_user` and the
      delete/update paths (`variable/service.py:34-84`,
      `environment/service.py:128-165`).
      (explicit per-member env grants `environments: [env_id]`, no wildcard for members;
      uniform RBAC, no env-name special-casing)
- [x] **P1 — Stop returning the member ID list to every member.** Filter
      `ProjectModel.users` from `GET /project/` or return a minimal DTO
      (`project/models.py:18`, `project/service.py:106-126`).
- [x] **P1 — Normalize email in `add_user`.** Use
      `payload.email.strip().lower()` to match register/login
      (`project/service.py:86`).
- [ ] **P1 — Add an audit trail for membership changes.** Who added/removed whom,
      when, and from which IP (see section 7).
- [ ] **P2 — Add ownership transfer** so a project is not orphaned when the
      owner leaves.

---

## 5. Input validation and data integrity

- [ ] **P0 — Allowlist variable names.** Reject names outside a safe set (e.g.
      `^[A-Za-z_][A-Za-z0-9_]*$`, or your chosen dotenv-safe set). This blocks
      newline/`=`/`#` injection into clients' `.env` files and fixes the AAD
      name ambiguity. Add the validator to `CreateVariableReq`
      (`variable/schemas.py:6-8`) and validate in update-by-name.
- [ ] **P0 — Add length limits.** Variable name, value, email, password,
      project/environment name, and request body. Set a reasonable max value
      size (e.g. 64 KB) and reject oversized payloads with `413/422`.
- [ ] **P0 — Add unique indexes at startup.** `users.email` (unique),
      `projects.(user_id, name)` (unique), `environments.(project_id, name)`
      (unique), `variables.(environment_id, name)` (unique). Create them in
      `app/db/mongodb.py` after connect and handle `DuplicateKeyError` in
      services. Acceptance: concurrent duplicate creates cannot succeed.
- [ ] **P1 — Validate ObjectIds.** Convert `ObjectId(...)` failures into `400`
      or `404` instead of a generic `500`. Add a helper used by every route.
- [ ] **P1 — Validate email format.** Use `pydantic.EmailStr` (or equivalent) in
      auth/project schemas.
- [ ] **P1 — Add quotas.** Max projects per user, environments per project,
      variables per environment, and total bytes per project.
- [ ] **P1 — Validate environment/project names consistently** on every route
      that accepts them (create and delete-by-name already have regexes; reuse
      them).
- [ ] **P2 — Normalize boolean/int variable values** consistently between create
      (`str | int | bool`) and update (`str`). Decide one representation.

---

## 6. API behavior, headers, and error semantics

- [ ] **P0 — Add `Cache-Control: no-store` to auth and all secret-bearing
      responses.** Current middleware only covers `/v1/variable`
      (`app/main.py:21-28`). Add `Pragma: no-cache` and `Vary: Authorization`.
- [ ] **P1 — Normalize authorization status codes.** Use `404` for
      not-found-or-not-a-member where possible, and `403` for authenticated but
      forbidden. Avoid `401` for project/environment not found
      (`environment/routes.py`, `project/routes.py`).
- [ ] **P1 — Add pagination** to projects, environments, and variables. Replace
      `to_list(length=None)` with bounded queries.
- [ ] **P1 — Add a request body size limit in the app** (not only nginx) and a
      JSON depth/size guard.
- [ ] **P1 — Sanitize validation errors.** FastAPI `422` responses echo invalid
      input; ensure secret values are never included in error responses.
- [ ] **P2 — Add `TrustedHostMiddleware`** with an explicit host allowlist.
- [ ] **P2 — Keep CORS closed** (no wildcard) unless a browser client is added.
- [ ] **P2 — Add security headers at the app layer** (`X-Content-Type-Options`,
      `Referrer-Policy`, `X-Frame-Options`) in addition to nginx.

---

## 7. Logging, audit, and monitoring

- [ ] **P0 — Add an audit log collection.** Record `auth.login`,
      `auth.login_failed`, `variable.read`, `variable.create`, `variable.update`,
      `variable.delete`, `project.share`, `member.remove`, `project.delete`,
      with user ID, project/environment ID, IP, user agent, and timestamp. Never
      log values.
- [ ] **P0 — Redact secrets and PII.** Remove email addresses from info logs
      (`auth/service.py:22,49`); use user IDs or hashed emails. Ensure exception
      logs never include request bodies.
- [ ] **P1 — Prevent log injection.** Variable/environment names are
      interpolated into logs (`variable/service.py:173,224`,
      `environment/service.py:32,170`). Validate names (section 5) and escape
      control characters.
- [ ] **P1 — Add alerting.** Alert on repeated login failures, mass variable
      reads, and membership changes.
- [ ] **P1 — Use structured JSON logs** with correlation IDs.

---

## 8. Database and persistence

- [ ] **P0 — Enable Mongo authentication and TLS** for the bundled and external
      deployments. Set a root/app user, require auth, and do not use
      `mongodb://mongo:27017` without credentials in production.
- [ ] **P1 — Restrict Mongo network access** to the API container only (already
      not published; add a dedicated network and firewall rules).
- [ ] **P1 — Document backup handling.** Encrypt backups, store the master key
      separately, define oplog retention, and test restore.
- [ ] **P1 — Project only needed fields** in queries (never return password
      hashes or wrapped keys accidentally).
- [ ] **P2 — Consider encryption at rest for the Mongo volume** (LUKS/EBS
      encryption) in addition to application-level encryption.

---

## 9. Deployment, transport, and secrets

Current files: `compose.yaml`, `Dockerfile`, `deploy/nginx/*`, `.env*`.

- [ ] **P0 — Make HTTPS the default.** Fail closed if certificates are missing,
      or bind HTTP to localhost only. The current fallback serves plaintext
      (`deploy/nginx/40-select-config.sh`).
- [ ] **P0 — Fix the HTTP→HTTPS redirect.** `https.conf` uses
      `https://$host$request_uri`, which is an open redirect. Use a configured
      hostname or `server_name` allowlist.
- [ ] **P0 — Rotate every secret that has ever been committed or shared.**
      A JWT secret was committed in git history (commit `706b344`). Treat it as
      compromised. Rotate the current `.env`/`.env.docker` values if the
      workspace has been shared.
- [ ] **P0 — Move secrets out of environment variables.** Use Compose
      `secrets:` or a KMS/secret manager so `docker inspect` and
      `/proc/<pid>/environ` do not expose them.
- [ ] **P1 — Narrow `--forwarded-allow-ips=*`.** Set it to the nginx
      container/network only (`Dockerfile` CMD).
- [ ] **P1 — Add nginx rate limiting.** `limit_req` for `/v1/auth/*` and a
      global burst limit. Keep `client_max_body_size`.
- [ ] **P1 — Harden Mongo container.** Non-root user, `security_opt`,
      `cap_drop`, read-only where possible, dedicated network.
- [ ] **P1 — Protect certificate private keys.** Ensure `privkey.pem` is `0600`
      and mounted read-only.
- [ ] **P2 — Add HSTS `includeSubDomains`** once all subdomains are HTTPS-only.
- [ ] **P2 — Hide upstream server headers** (`proxy_hide_header Server`).

---

## 10. Repository and operational hygiene

- [x] **P0 — Fix `.gitignore`.** It only ignores `.env` and `.env.docker`;
      add `.env*` (with `!.env.example` / `!.env.docker.example`). Add
      `*.pem`, `*.key`, and `deploy/certs/*`.
- [ ] **P0 — Add secret scanning** (gitleaks/trufflehog) to CI/pre-commit.
- [ ] **P0 — Add dependency auditing** (`uv audit`/`pip-audit`/Dependabot) and
      pin/update `cryptography`, `pyjwt`, `pymongo`, `fastapi`.
- [ ] **P1 — Add a security section to the README** covering HTTPS, key
      separation, backups, and rotation.
- [ ] **P1 — Add a SECURITY.md** with a disclosure contact and supported
      versions.

---

## 11. Cross-repo tasks (CLI side)

These need changes in `../sharenv`; keep the contracts in sync.

- [ ] **P0 — Define the variable-name regex once** and enforce it in both
      `CreateVariableReq` and the CLI parser/writer.
- [ ] **P0 — Define the share/invite flow** (`POST /project/{id}/invitations`,
      `POST /invitations/{token}/accept`) and update the CLI `add` command.
- [ ] **P0 — Define the logout/revocation endpoint** and add a CLI `logout`.
- [ ] **P0 — Define the email-verification flow** and add CLI handling for
      `403 email_not_verified`.
- [ ] **P1 — Return project `name` and `owner` in `GET /project/`** so the CLI
      can show them before push/pull.
- [ ] **P1 — Return role information** so the CLI can hide destructive actions
      for readers.

---

## 12. Verification checklist

- [ ] **P0 — Auth tests:** unknown email and wrong password return identical
      responses; rate limits trigger; unverified users cannot log in.
- [ ] **P0 — Authorization tests:** non-member cannot read/write/delete; reader
      cannot write/delete; removed member loses access immediately.
- [ ] **P0 — Crypto tests:** rotation, tamper, AAD mismatch, per-project
      isolation.
- [ ] **P0 — Injection tests:** variable names with `\n`, `=`, `#`, `/`, and
      spaces are rejected.
- [ ] **P0 — Concurrency tests:** duplicate registration/project/env/variable
      creates return `409`, not duplicates.
- [ ] **P1 — Header tests:** `Cache-Control: no-store` on auth/variable
      responses; no secret in logs.
- [ ] **P1 — Deployment tests:** HTTP-only startup fails closed; redirect uses a
      fixed host; Mongo requires auth.
