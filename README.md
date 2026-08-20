# Stellic-Pathfinders
Pathfinders Challenge Project

## Deploying to Vercel

The repo ships a `vercel.json`: `Compass Planner.html` is served as a static
file at `/`, and the FastAPI app runs as one serverless function mounted at
`/api`. Both come from the same origin, so the frontend calls `/api/...` with
no CORS involved — it picks that base automatically and still talks to
`http://localhost:8000` when opened locally.

Two environment variables must be set in the Vercel project before the
deployment is usable:

| Variable | Why |
|---|---|
| `DATABASE_URL` | A Postgres URL. Serverless filesystems are read-only except `/tmp`, and `/tmp` is per-instance and cleared on cold starts, so SQLite there silently loses every account. `postgres://` and `postgresql://` are rewritten to the psycopg driver for you. |
| `SECRET_KEY` | Signs session tokens. Without it the app falls back to a public development key, and anyone can forge a login. Generate with `python3 -c "import secrets;print(secrets.token_urlsafe(48))"`. |

The app boots without either one and logs a loud warning for each, so a missing
variable shows up in the runtime logs rather than as a blank 500.

Tables are created on startup when they are absent, because there is nowhere to
run `alembic upgrade` on a serverless host. That only creates missing tables —
it will not add a column to a table an older revision already created, so run
`alembic upgrade head` yourself when migrating an existing database.
