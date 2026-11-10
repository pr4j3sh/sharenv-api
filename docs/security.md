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
validation of values impossible. The current design keeps server-side
encryption with per-project data keys wrapped by versioned master keys (see
`docs/key-rotation.md` for the rotation runbook), not to claim E2E properties
the system does not have.

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

| Class                  | Examples                                                                          | At rest                                                                                                                     | Who can read it                                                     |
| ---------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Secret**             | Variable values                                                                   | AES-256-GCM ciphertext (`value_enc`)                                                                                        | Any member of the project, the API process, the operator, host root |
| **Sensitive metadata** | Variable names, environment names, project names, member user IDs, account emails | Plaintext                                                                                                                   | The same parties as secrets, plus anyone with database access       |
| **Credentials**        | Password hashes, HMAC-hashed verification OTPs, `JWT_SECRET`, master encryption keys (`ENCRYPTION_KEYS_JSON`/`ENCRYPTION_KEYS_FILE`) | Argon2id password hashes and peppered OTP hashes in `users`; keys outside the database — the master key registry is a Docker secret file (`deploy/secrets/encryption_keys.json`), `JWT_SECRET` is still a container environment variable | The API process and host root; never returned by the API            |
| **Operational**        | ObjectIds, timestamps, `key_version`, record sizes                                | Plaintext                                                                                                                   | Anyone with database access                                         |

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
- **Keys are never stored in the database in usable form.** Each project has a
  random data key used to encrypt its variable values; it is stored in
  `projects.data_key` wrapped (encrypted) under a master key, together with
  the master key version that wrapped it (`projects.key_version`). The master
  key registry maps versions to keys and is configured through
  `ENCRYPTION_KEYS_JSON` (inline, local development) or
  `ENCRYPTION_KEYS_FILE` (a Docker secret in the compose deployment);
  `ENCRYPTION_KEY_VERSION` selects the active version used for new writes.
  `JWT_SECRET` is loaded from the container environment today. See the gaps
  table.
- **Verification OTPs are peppered, not plaintext.** Account verification
  codes are stored as HMAC-SHA256 keyed with `JWT_SECRET`, so a database-only
  attacker cannot use them to verify accounts. They are short-lived (10
  minutes by default) and are delivered by email through the configured
  provider (`smtp` or `resend`), which therefore sees recipient addresses and
  OTPs. When `EMAIL_PROVIDER=none` no OTP is generated at all and verification
  is impossible — see "Unverified operation" below.

## What the server can see

The API can, by design:

- read every variable value in plaintext while handling a request;
- read all names, project structure, membership, and account emails;
- verify passwords against stored Argon2id hashes;
- deliver account verification emails through the configured provider
  (`smtp` or `resend`), which sees recipient addresses and the OTPs;
- mint a valid bearer token for any user id;
- read its own encryption and signing keys.

The API cannot:

- protect values from itself, its operator, or host root;
- prevent a member who is allowed to read a value from copying it;
- recover values if the master key registry is lost (there is no key escrow);
- detect that the database was rolled back to an older snapshot;
- prove to a client that a returned value is the one that was stored.

## Threat model

### Database-only attacker

_Scenario: a stolen dump or backup, read-only database credentials, or a
compromised database host._

- Gets: ciphertext values, plaintext names and structure, account emails,
  Argon2id password hashes, peppered verification OTP hashes, membership
  lists, and wrapped per-project data keys.
- Can: enumerate projects, environments, and variable names; attempt offline
  password guessing; delete or modify records if the access is writable;
  replay an existing ciphertext into a record with the same AAD; restore an
  old snapshot.
- Cannot: decrypt values without a master key, which is not stored in the
  database; forge a new valid ciphertext without the key; recover a password
  that resists Argon2id guessing; verify an account with a stolen OTP hash
  because it is peppered with a server-side secret.

Limits: AES-GCM authenticates each record with an AAD binding
`project_id`, `environment_id`, `name`, and `key_version`, so a ciphertext
cannot be moved between projects or relabelled with a different key version.
It can still be replayed into a record that shares all four fields (for
example after the original was deleted and re-created), and a database
attacker can delete or corrupt records. The database is not an integrity
authority.

### Stolen bearer token

_Scenario: a token copied from the CLI keyring, process memory, logs, or a
compromised client machine._

- Gets: the full access of that user until the token is revoked or expires.
- Can: list projects and, subject to role and environment grants, read and
  decrypt values in projects the user belongs to; writers can create/update/
  delete variables and create/delete environments in their granted environments.
  The owner can create invitations, manage member access, remove members, and
  delete projects the user owns (all with re-authentication where required).
- Cannot: change the account password (there is no endpoint), or use the token
  after `exp`, after logout, or after the user is deleted.
- Sensitive owner actions (`PUT /v1/project/{id}` share, project deletion)
  require the caller's current password in addition to a valid token.

Current state: access tokens carry `jti`, `ver` (the user's `token_version`),
and `typ: "access"`; refresh tokens carry `typ: "refresh"` and are
single-use and rotated on `POST /v1/auth/refresh`. `get_current_user_id`
decodes the token and re-checks the user and `token_version` on every request,
so `POST /v1/auth/logout` (which bumps `token_version`), a refresh-token
replay (which revokes the whole chain), and user deletion all invalidate
issued tokens immediately. The default access-token lifetime is 15 minutes
(`JWT_EXPIRY`); refresh tokens expire after 30 days
(`REFRESH_TOKEN_EXPIRY_DAYS`). MFA/TOTP and per-token (jti-based) revocation
are not yet implemented. See `plan.md` §3.

### Malicious or curious project member

_Scenario: the owner invites a user who accepts, or a member's account is
taken over._

- Gets: access to the project and only the environments explicitly granted to
  that member.
- Can: a **reader** can list/read values in granted environments; a **writer**
  can additionally create/update/delete variables and create/delete environments
  (scoped to granted environments). An owner has full control.
- Cannot: non-owners cannot invite, change member access, remove members, or
  delete the project. A member cannot access environments not granted to them.
- Membership requires the invitee's consent (accepting a token as the matching,
  verified — or, in `EMAIL_PROVIDER=none` mode, merely account-holder — user).
  The owner can remove a member, change their granted
  environments/role, or the member can leave; access is enforced from DB
  membership/grants on every request, so revocation and grant changes take
  effect immediately. `GET /v1/project/` returns the caller's role but not the
  member list.

There is still no membership-change audit trail (see `plan.md` §4/§7). The
invitation (token) is returned to the owner at creation time for out-of-band
delivery, and additionally emailed when a provider is configured (best-effort).
Per-environment
access is an explicit grant list (no wildcard for members); uniform RBAC applies
(no special-casing by environment name).

### Compromised host or API process

_Scenario: remote code execution in the API, a compromised container image, or
root on the host._

- Gets: the master key registry, `JWT_SECRET`, MongoDB credentials, and the
  API code.
- Can: decrypt every value, mint tokens for any user, read plaintext from
  process memory, modify responses, and persist access.
- Equals: full compromise of every secret in the deployment. Host root also
  reaches the database volume and any backups on the host.

Each project has its own data key, so a leaked single project key cannot
decrypt another project's values. But there is no hardware-backed key
boundary and no KMS: the master key registry wraps every project key, so one
leaked master key still decrypts every project it ever wrapped.

## Unverified operation (`EMAIL_PROVIDER=none`)

With no mail provider configured, verification is impossible, so the deployment
operates with weakened identity guarantees. This mode exists for orgs that
cannot or do not want to run/point at a mail relay; it must not be exposed to
an untrusted network.

- New accounts are created unverified and **may log in**; login reports
  `email_verified: false` in the response (also in `/v1/auth/refresh`).
- Invitation accept requires token possession plus the email match, but no
  verification (nobody can ever become verified in this mode).
- Invitation tokens are returned at creation time for out-of-band delivery;
  the copy-link is a legitimate first-class channel (possession of the token
  is the bearer proof, bound to the invited email string).
- Identities are self-asserted: anyone who can reach the API may claim any
  address. The deployment therefore **requires** network-level access control
  (VPN, nginx allowlist, SSO proxy) and organizational trust of members.
- The sharenv CLI warns on sensitive actions (invitations, member changes,
  project delete, variable push/delete) while the caller's account is
  unverified. Warnings are advisory, not enforcement; a server-wide
  unverified deployment must not be treated as authenticating mailboxes.
- Switching later to `smtp`/`resend` re-enables verification (existing users
  verify via the resend-OTP flow) with no data migration.

## Crypto-shredding

Deleting a project destroys its wrapped data key. `projects.data_key` lives on
the project document, and project deletion (by id or by name) removes the
variables, environments, and the project document itself, so nothing
decryptable remains in the live database. This is the intended destruction
property.

Caveats:

- MongoDB backups and the oplog can still contain both the ciphertext and the
  wrapped data key, so deletion does not destroy those copies. Destroying old
  backups' data requires rotating the master key (see
  [docs/key-rotation.md](key-rotation.md)) and letting backups taken before the
  rotation expire, because only the old master key can unwrap those wrapped
  data keys.
- Rotating a project's data key alone (re-wrapping under a fresh data key) is
  not implemented; master key rotation re-encrypts under the same per-project
  data key.

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
What deletion destroys and what survives in backups is covered in
[Crypto-shredding](#crypto-shredding); backup handling beyond that is not yet
documented. See `plan.md` §8.

### Operator and insider

The operator is trusted with plaintext by definition of the server-side model.
An operator can read every value through the API or by using the keys. This is
the intended trust boundary, not a vulnerability, but it must be stated in any
deployment or compliance discussion.

## Current gaps

Each gap is tracked in `plan.md`; this table records the state at the time of
writing.

| Gap                                                                                 | Impact                                                                                                | Fix    |
| ----------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ------ |
| `JWT_SECRET` still lives in `.env`/container environment                             | `docker inspect` and `/proc/<pid>/environ` expose it                                                  | §9     |
| Verification email depends on the configured provider (`smtp`/`resend`)      | Provider compromise exposes recipient addresses and OTPs; `none` mode has no verification at all (see "Unverified operation") | §3     |
| No MFA/TOTP                                                                         | A stolen or guessed password alone is enough after verification                                       | §3     |
| Auth rate limiting is in-memory and per-process                                      | Counters reset on restart and are not shared across uvicorn workers (nginx adds a coarse outer limit)  | §3, §9 |
| Per-email login lockout is an account-availability DoS surface                       | An attacker can lock out any email address by sending failures                                        | §3     |
| No membership-change audit trail                                                    | Limited attribution for invitations, role/grant changes, and removals                                  | §4, §7 |
| Variable names are not validated                                                    | Newline/`=`/`#` injection into clients' `.env` files; AAD ambiguity                                   | §5     |
| No unique indexes; `ObjectId` not validated                                         | Duplicate races; invalid ids return `500`                                                             | §5     |
| `Cache-Control: no-store` only on `/v1/variable`                                    | Auth and project/environment responses may be cached                                                  | §6     |
| No audit log; some PII/names still appear in logs                                   | Limited detection/attribution; metadata may leak into logs                                            | §7     |
| Bundled MongoDB has no authentication or TLS                                        | Anyone who can reach it reads everything                                                              | §8     |
| HTTP-only fallback; `Host`-based redirect                                           | Plaintext exposure and open redirect                                                                  | §9     |
| Secrets may exist in git history                                                    | Key and token leakage through the repository                                                          | §10    |
| Backup handling is undocumented                                                     | Backups may be unprotected or unencrypted                                                             | §8     |

## Assumptions

- The operator is trusted with plaintext values.
- TLS terminates at nginx and clients verify the certificate.
- MongoDB is reachable only by the API, never directly from the internet.
- Host root is trusted; a root compromise is outside the protection claims.
- `DEBUG=False` in production. `DEBUG=True` and `EMAIL_PROVIDER=console` skip
  email delivery and log verification OTPs/invitation tokens instead; they
  exist only for local development.
- When `EMAIL_PROVIDER=none`, the API is only reachable on a trusted network
  (VPN/allowlist/SSO proxy); identity is self-asserted in this mode.
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
- `docs/key-rotation.md` — master key rotation runbook.
- `docs/self-hosting.md` — deployment and TLS setup.
- `plan.md` — remediation roadmap referenced throughout this document.
- CLI trust model: <https://github.com/pr4j3sh/sharenv/blob/main/docs/security.md>.
