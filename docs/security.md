# sharenv-api security model

This document describes what the `sharenv-api` server protects, what it does
not protect, and the assumptions behind those claims. It is the trust model
that the rest of the security work depends on.

Companion document: the CLI trust model lives at
<https://github.com/pr4j3sh/sharenv/blob/main/docs/security.md>.

## Decision: server-side encryption

`sharenv` uses **server-side encryption**. It is **not end-to-end
encrypted**.

- Variable values are sent to the API as JSON over TLS.
- The API encrypts values before storing them in MongoDB and decrypts them
  before returning them to an authorized client.
- The server therefore sees every value in plaintext during normal operation.
- **Server compromise means all secrets are compromised.** A compromised API
  process, a compromised host, or a malicious operator can read every value in
  every project.

End-to-end encryption (client-held per-project keys, opaque blobs in the API)
is not implemented. Moving to it would require a CLI-side key store and an
out-of-band key distribution design for sharing, and would make server-side
validation of values impossible. The planned direction is to keep server-side
encryption and strengthen it with per-project data keys and rotation (see
`plan.md` §2), not to claim E2E properties the system does not have.

Do not describe this system as "zero-knowledge", "end-to-end encrypted", or
"the server cannot read your secrets".

## Data flow

Push:

```text
.env.*  --plaintext-->  sharenv CLI  --TLS + bearer token-->  sharenv-api
                                                                    |
                                                        encrypt (AES-256-GCM)
                                                                    |
                                                                 MongoDB
```

Pull:

```text
MongoDB  -->  sharenv-api (decrypts)  --TLS-->  sharenv CLI  -->  .env.* (plaintext)
```

There is no key material in the CLI. All key material is held by the server.

## Data classification

| Class                  | Examples                                                                          | At rest                                                                                    | Who can read it                                                     |
| ---------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| **Secret**             | Variable values                                                                   | AES-256-GCM ciphertext (`value_enc`)                                                       | Any member of the project, the API process, the operator, host root |
| **Sensitive metadata** | Variable names, environment names, project names, member user IDs, account emails | Plaintext                                                                                  | The same parties as secrets, plus anyone with database access       |
| **Credentials**        | Password hashes, `JWT_SECRET`, `ENCRYPTION_KEY`                                   | Password hashes in `users`; keys outside the database (`.env`/container environment today) | The API process and host root; never returned by the API            |
| **Operational**        | ObjectIds, timestamps, `key_version`, record sizes                                | Plaintext                                                                                  | Anyone with database access                                         |

Decisions recorded here:

- **Values are secret.** They are never stored in plaintext and are never
  logged.
- **Names and metadata are sensitive, but not secret.** Variable names can
  reveal intent even without values (`STRIPE_SECRET_KEY`,
  `INTERNAL_ADMIN_TOKEN`), and project/environment names reveal structure.
  They are deliberately left in plaintext in this phase because they are used
  for lookups, uniqueness, and as AAD. Encrypting them would require blind
  indexes and would not protect against the server operator. Treat the names
  as confidential to the deployment, not as secrets.
- **Password hashes are credentials, not secrets.** They are Argon2id hashes
  produced by `pwdlib` and are never returned. A database-only attacker can
  attempt offline guessing against them; weak or reused passwords will fall.
- **Keys are never stored in the database.** `ENCRYPTION_KEY` and
  `JWT_SECRET` are loaded from configuration (`.env` or the container
  environment) today. See the gaps table.

## What the server can see

The API can, by design:

- read every variable value in plaintext while handling a request;
- read all names, project structure, membership, and account emails;
- verify passwords against stored Argon2id hashes;
- mint a valid bearer token for any user id;
- read its own encryption and signing keys.

The API cannot:

- protect values from itself, its operator, or host root;
- prevent a member who is allowed to read a value from copying it;
- recover values if `ENCRYPTION_KEY` is lost (there is no key escrow);
- detect that the database was rolled back to an older snapshot;
- prove to a client that a returned value is the one that was stored.

## Threat model

### Database-only attacker

_Scenario: a stolen dump or backup, read-only database credentials, or a
compromised database host._

- Gets: ciphertext values, plaintext names and structure, account emails,
  Argon2id password hashes, membership lists.
- Can: enumerate projects, environments, and variable names; attempt offline
  password guessing; delete or modify records if the access is writable;
  replay an existing ciphertext into a record with the same AAD; restore an
  old snapshot.
- Cannot: decrypt values without `ENCRYPTION_KEY`, which is not stored in the
  database; forge a new valid ciphertext without the key; recover a password
  that resists Argon2id guessing.

Limits: AES-GCM authenticates each record, but the AAD currently binds only
`environment_id:name`. A ciphertext can be moved between records that share
both, and `key_version` is not authenticated. The database is not an integrity
authority.

### Stolen bearer token

_Scenario: a token copied from the CLI keyring, process memory, logs, or a
compromised client machine._

- Gets: the full access of that user until the token expires.
- Can: list projects, read and decrypt every value in every project the user
  belongs to, create/update/delete variables, delete environments, add members
  to projects the user owns, and delete projects the user owns.
- Cannot: change the account password (there is no endpoint), or use the token
  after `exp`.

Current limitations: tokens are stateless, carry no `jti`, and cannot be
revoked. The default lifetime is 60 minutes (`JWT_EXPIRY`). There is no logout
endpoint and no refresh-token rotation. Deleting a user does not invalidate an
already-issued token because `get_current_user_id` does not re-check the
`users` collection. See `plan.md` §3.

### Malicious or curious project member

_Scenario: the owner adds a user, or a member's account is taken over._

- Gets: read access to every environment in the project.
- Can: read and decrypt all values, create and update variables, delete
  variables, and delete environments. Membership is currently a flat list with
  no roles.
- Cannot: add other members or delete the project; those are owner-only.
- Can also: see the full member id list through `GET /v1/project/`.

There is no invitation or consent step, no member removal endpoint, and no
audit trail, so a member can silently exfiltrate values and the owner cannot
revoke access. See `plan.md` §4.

### Compromised host or API process

_Scenario: remote code execution in the API, a compromised container image, or
root on the host._

- Gets: `ENCRYPTION_KEY`, `JWT_SECRET`, MongoDB credentials, and the API code.
- Can: decrypt every value, mint tokens for any user, read plaintext from
  process memory, modify responses, and persist access.
- Equals: full compromise of every secret in the deployment. Host root also
  reaches the database volume and any backups on the host.

There is no hardware-backed key boundary, no KMS, and no per-project key
isolation today. One leaked `ENCRYPTION_KEY` decrypts every project.

### Compromised client machine

_Scenario: malware or another process running as the CLI user._

- Gets: plaintext `.env.*` files, the bearer token from the OS keyring, and
  plaintext values while the CLI is running.
- Can: act as the user against the API and read local copies outside the
  CLI's control (editors, history, swap, backups, snapshots).

### Network attacker

_Scenario: an attacker on the path between the CLI and the API._

- With HTTPS: TLS 1.2/1.3 protects credentials and values in transit. The
  client verifies the certificate against the platform trust store.
- With plain HTTP: everything, including passwords, tokens, and values, is
  readable and modifiable. The bundled deployment still starts in HTTP-only
  mode when certificates are absent, and the HTTP-to-HTTPS redirect uses the
  request `Host` header. See `plan.md` §9.

### Database administrator or backup thief

Same access as the database-only attacker, plus the ability to restore old
snapshots and read the oplog if it is enabled. Backups contain ciphertext and
metadata; the key must be stored separately for backups to remain protected.
Backup handling is not yet documented. See `plan.md` §2 and §8.

### Operator and insider

The operator is trusted with plaintext by definition of the server-side model.
An operator can read every value through the API or by using the keys. This is
the intended trust boundary, not a vulnerability, but it must be stated in any
deployment or compliance discussion.

## Current gaps

Each gap is tracked in `plan.md`; this table records the state at the time of
writing.

| Gap                                                                         | Impact                                                                                                | Fix    |
| --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------ |
| One global `ENCRYPTION_KEY`; `key_version` is stored but ignored on decrypt | One key leak decrypts every project; rotation breaks old values                                       | §2     |
| AAD binds only `environment_id:name`                                        | Ciphertext can be relabelled or replayed between same-named records; key version is not authenticated | §2     |
| Key and JWT secret live in `.env`/container environment                     | `docker inspect` and `/proc/<pid>/environ` expose them                                                | §2, §9 |
| No email verification; registration returns a token immediately             | An attacker can register a victim's email and use the account                                         | §3     |
| Login distinguishes unknown email (`404`) from wrong password (`401`)       | Account enumeration                                                                                   | §3     |
| No rate limiting or lockout                                                 | Brute force and password spraying                                                                     | §3     |
| No revocation, logout, or refresh tokens                                    | A stolen token works until expiry                                                                     | §3     |
| Flat membership: no roles, consent, or removal                              | Any member can write and delete; owner can grant access silently                                      | §4     |
| Variable names are not validated                                            | Newline/`=`/`#` injection into clients' `.env` files; AAD ambiguity                                   | §5     |
| No unique indexes; `ObjectId` not validated                                 | Duplicate races; invalid ids return `500`                                                             | §5     |
| `Cache-Control: no-store` only on `/v1/variable`                            | Auth and project/environment responses may be cached                                                  | §6     |
| No audit log; emails and names are logged                                   | No detection or attribution; metadata leaks into logs                                                 | §7     |
| Bundled MongoDB has no authentication or TLS                                | Anyone who can reach it reads everything                                                              | §8     |
| HTTP-only fallback; `Host`-based redirect; no HSTS or rate limit            | Plaintext exposure and open redirect                                                                  | §9     |
| Secrets may exist in git history; `.gitignore` is narrow                    | Key and token leakage through the repository                                                          | §10    |
| Backup handling is undocumented                                             | Backups may be unprotected or unencrypted                                                             | §2, §8 |

## Assumptions

- The operator is trusted with plaintext values.
- TLS terminates at nginx and clients verify the certificate.
- MongoDB is reachable only by the API, never directly from the internet.
- Host root is trusted; a root compromise is outside the protection claims.
- Clients are trusted with the values they are authorized to pull.
- No compliance guarantee is made (for example, for regulated data) beyond
  the controls described here.
- Backups, if enabled, are encrypted and stored separately from the key. This
  is a requirement, not yet an implemented control.

## Reporting a vulnerability

Use GitHub Security Advisories:
<https://github.com/pr4j3sh/sharenv-api/security/advisories/new>.

Do not open a public issue for a vulnerability, and do not include real tokens,
passwords, or environment values in a report. A minimal reproduction with
placeholder secrets is enough.

## Related documents

- `docs/security-review.md` — checklist for reviewing new routes.
- `docs/self-hosting.md` — deployment and TLS setup.
- `plan.md` — remediation roadmap referenced throughout this document.
- CLI trust model: <https://github.com/pr4j3sh/sharenv/blob/main/docs/security.md>.
