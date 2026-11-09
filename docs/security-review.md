# Security review checklist

Use this checklist for every new or changed route, service, or background job
that touches accounts, projects, environments, or variables. It assumes the
trust model in `docs/security.md`: values are encrypted server-side and the
operator is trusted with plaintext.

A change is not ready to merge until every applicable item is checked or the
exception is written down in the PR description.

## Authentication

- [ ] The route depends on `get_current_user_id`; there is no unauthenticated
      path that returns project or variable data.
- [ ] Missing or invalid credentials return `401` with
      `WWW-Authenticate: Bearer`, not `403` and not `500`.
- [ ] The handler does not accept a user id, project id, or role from the
      request body when it can be derived from the token.
- [ ] Tokens are never logged, echoed in errors, or returned anywhere except
      the login/register response.
- [ ] If the change adds a new token type or claim, it is validated explicitly
      and the algorithm is allowlisted.

## Authorization

- [ ] Every project, environment, and variable id from the path is resolved to
      its owning project before any read or write.
- [ ] Membership is checked with the same owner-or-member query used elsewhere
      (`{"$or": [{"user_id": user_id}, {"users": user_id}]}`), not by trusting
      a client-supplied project id.
- [ ] Owner-only actions (add member, delete project, future member removal)
      check `projects.user_id`, not just membership.
- [ ] Role rules are enforced once roles exist: readers cannot create, update,
      or delete; writers cannot manage membership or delete the project.
- [ ] Deleting an environment or project also deletes its children, and the
      operation is not reachable by a non-owner unless intended.
- [ ] Cross-tenant access is tested with a second user's token, not only by
      reading the code.

## Input validation

- [ ] Path ids are converted with a helper that turns an invalid `ObjectId`
      into `400`/`404`, not a `500`.
- [ ] Variable names match the shared allowlist regex. Project and
      environment names match `[a-z0-9_-]+` on every route that accepts them.
- [ ] Name, value, email, and password lengths are bounded. Oversized bodies
      are rejected with `413`/`422`.
- [ ] Email is trimmed and lowercased before lookup, comparison, and storage.
- [ ] Boolean/integer variable values are normalized consistently between
      create and update.
- [ ] Request models reject unknown or extra fields where the client contract
      allows it.
- [ ] New indexes are created at startup and `DuplicateKeyError` is translated
      to `409` instead of a `500`.

## Cryptography and data handling

- [ ] Values are encrypted before insert and decrypted only at the response
      boundary. No plaintext value is written to Mongo, logs, or errors.
- [ ] New ciphertext uses the active key version and records it in
      `key_version`.
- [ ] The AAD includes every field that must not be relabelled (environment,
      name, and eventually project id and key version).
- [ ] A single undecryptable record does not fail the whole list response.
- [ ] Key material comes from config/secrets, never from the repository, a
      request, or a log line.
- [ ] Deleting a project or variable does not leave plaintext copies in
      temporary files or logs.

## Responses

- [ ] The response model is explicit; it does not serialize the stored
      document wholesale.
- [ ] Password hashes, `value_enc`, `key_version`, wrapped keys, and internal
      fields are never returned.
- [ ] Member lists are filtered to what the caller needs; a plain member does
      not receive the full user-id list.
- [ ] Secret-bearing responses set `Cache-Control: no-store` (and ideally
      `Pragma: no-cache` and `Vary: Authorization`).
- [ ] Error responses do not reveal whether an account, project, or variable
      exists unless the caller is already authorized to know.

## Logging and audit

- [ ] No variable values, passwords, tokens, or password hashes are logged.
- [ ] Emails are replaced with user ids or hashed identifiers in info logs.
- [ ] Names interpolated into logs are validated and stripped of control
      characters (log injection).
- [ ] Sensitive mutations emit an audit event: who, what, which
      project/environment, IP, user agent, timestamp.
- [ ] Exception handlers log a correlation id and never the request body.
- [ ] Failed authorization and failed login attempts are observable.

## Errors and headers

- [ ] Status codes follow the neighboring handlers: `401` unauthenticated,
      `403` authenticated but forbidden, `404` not found or not a member,
      `409` conflict.
- [ ] Validation errors never echo secret values back to the client.
- [ ] Security headers are not weakened (`X-Content-Type-Options`,
      `Referrer-Policy`, `X-Frame-Options`).
- [ ] CORS stays closed unless a browser client is added.

## Tests

- [ ] Authorization matrix: owner, member, non-member, and removed member
      against read, create, update, and delete.
- [ ] Injection: variable names containing `\n`, `=`, `#`, `/`, spaces, and
      control characters are rejected.
- [ ] Concurrency: duplicate register/project/environment/variable creates
      return `409` and leave one record.
- [ ] Crypto: tamper detection, AAD mismatch, wrong key version, rotation
      round-trip, per-project isolation.
- [ ] Headers: `Cache-Control: no-store` on secret-bearing responses.
- [ ] Logs: a failed request with a secret value produces no value in the log
      output.

## Do not merge if

- A new route returns project or variable data without a membership check.
- A secret value can reach a log, an error body, or a cache.
- A new key or token path bypasses the configured algorithm/key allowlist.
- A `500` is the expected outcome for bad user input or an invalid id.
- The PR changes the trust model in `docs/security.md` without updating that
  document.

## Sign-off

- Reviewer:
- Date:
- Exceptions (with justification):
