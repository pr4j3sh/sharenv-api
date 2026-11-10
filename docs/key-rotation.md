# Master key rotation runbook

How keys are laid out:

- Each project has a random data key used to encrypt its variable values. It
  is stored on the project document (`projects.data_key`) wrapped with a
  master key, alongside the master key version used
  (`projects.key_version`).
- Each variable records the master key version it was encrypted under
  (`variables.key_version`); that version is also bound into the value's AAD,
  together with the project id, environment id, and variable name.
- The registry maps key versions to 32-byte keys and is configured through
  `ENCRYPTION_KEYS_JSON` (inline JSON, local development) or
  `ENCRYPTION_KEYS_FILE` (a JSON file path; the Docker deployment mounts it as
  a secret). `ENCRYPTION_KEY_VERSION` selects the active version: new writes
  always use it, older versions stay available for decryption.

## Rotating the master key

1. Generate the new key:

   ```bash
   openssl rand -base64 32
   ```

2. Add it to the registry under the next version, **keeping the old key(s)** so
   existing data stays decryptable. For the Docker deployment, edit
   `deploy/secrets/encryption_keys.json`:

   ```json
   {"1": "<old base64 key>", "2": "<new base64 key>"}
   ```

   For local development, update `ENCRYPTION_KEYS_JSON` in `.env`.

3. Make the new version active:

   ```env
   ENCRYPTION_KEY_VERSION=2
   ```

4. Restart the API so it loads the updated registry
   (`docker compose up -d --build`, or restart your local server). Values
   written after this step use version 2; values written before it remain
   readable because version 1 is still configured.

5. Re-encrypt the stored data (from the repository root):

   ```bash
   uv run python -m scripts.rotate_keys --dry-run   # report only
   uv run python -m scripts.rotate_keys             # apply
   ```

   The script re-wraps every project data key under the active version and
   re-encrypts every variable value so its `key_version` and AAD match. It
   updates one document at a time and skips anything already on the active
   version, so it is idempotent and resumable: a crashed run is re-run as-is.

6. Verify a project's values still decrypt through the API, then remove the
   old version from the registry and restart once more. Until you do, the old
   key can still decrypt pre-rotation data (and any backups that contain it).

## Notes and failure modes

- Removing the old version from the registry before the script has run leaves
  pre-rotation values permanently undecryptable. `GET` returns them with
  `undecryptable: true` and the API logs the failure; there is no key escrow.
- If the script cannot unwrap a project's data key (its version is missing
  from the registry), it logs an error, skips that project, and exits non-zero.
  Re-add the missing version and re-run.
- A new project key does not touch other projects: data keys are per-project,
  so only the master key rotation described here is global.
- Backups and the MongoDB oplog can still contain ciphertext (and wrapped data
  keys) encrypted under the old key. Rotation does not destroy those copies;
  see the crypto-shredding section in `docs/security.md`.
- The AAD binds `project_id`, `environment_id`, `name`, and `key_version`, so
  ciphertext cannot be moved between projects or relabelled with another
  version. Renaming a variable or moving it between environments requires
  re-encryption (create a new variable).
