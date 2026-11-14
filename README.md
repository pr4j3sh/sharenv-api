# sharenv-api

Self-hosted API Server for securely managing, syncing, and sharing project
environment variables. The server behind [`sharenv`](https://github.com/pr4j3sh/sharenv) CLI.

## Documentation

- [Self-hosting with Docker](docs/self-hosting.md)
- [Running from source](docs/development.md)
- [Key rotation](docs/key-rotation.md)

## Security

> Values are encrypted server-side, not end-to-end. The API decrypts them before
> returning them, so a compromised server or operator can read every value. Read
> the trust model and data classification in [docs/security.md](docs/security.md)
> before storing real production secrets.
