# ADR 0019: First-run admin password and browser sessions

- Status: Accepted
- Date: 2026-11-26
- Deciders: polygate maintainers

## Context

The admin console used a static `ADMIN_TOKEN` bearer credential. That made the first visit
dependent on copying an environment secret into the browser, and there was no way to sign in with a
password. The token also had no expiry or per-browser session model.

## Decision

- The admin UI starts with `GET /admin/auth/status`. When no password exists, it shows a first-run
  setup form; `POST /admin/auth/setup` stores a salted scrypt hash and creates a browser session.
- Later visits show a password form; `POST /admin/auth/login` verifies the password and returns a
  random bearer session token. Sessions are stored hashed server-side for seven days.
- Logout revokes the server session and clears the browser token.
- `ADMIN_TOKEN` remains a legacy API credential for automation; the browser UI does not ask for it.
  A missing password with no usable session returns `428 Precondition Required` with a
  setup-required message, not a 503 outage loop.
- The first person who can reach an unconfigured instance can set the password. Bind the service to
  localhost or a trusted network until the password is set.

## Consequences

- The browser never needs the environment `ADMIN_TOKEN`.
- Password hashes and session digests are stored in SQLite; both the database and `.env` remain
  secrets.
- There is no password-reset UI. Recovery is an operator action on the database/environment.
- Login rate limiting and multi-user roles are out of scope; this is a single-admin local console.

## References

- `backend/src/polygate/password.py`, `backend/src/polygate/api/account.py`,
  `backend/src/polygate/storage.py`, `frontend/src/pages/Login.tsx`
