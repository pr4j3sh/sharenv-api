# sharenv-api

Self-hosted API for securely managing, syncing, and sharing project
environment variables — the server behind the
[`sharenv`](https://github.com/pr4j3sh/sharenv) CLI.

## Documentation

- [Self-hosting with Docker](docs/self-hosting.md)
- [Running from source](docs/development.md)
- [Key rotation](docs/key-rotation.md)

## Security

Values are encrypted server-side, not end-to-end: the API decrypts them before
returning them, so a compromised server or operator can read every value. Read
the trust model and data classification in [docs/security.md](docs/security.md)
before storing real production secrets.

Changes to routes and services must pass [docs/security-review.md](docs/security-review.md).
