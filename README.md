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

## Deploying the frontend to Cloudflare

Cloudflare serves the page; the API stays on a host that can run it. That split
is forced, not stylistic: the API is FastAPI on SQLAlchemy and psycopg, and
Python Workers run under Pyodide, which has no PostgreSQL driver — a Worker is
expected to reach a database over HTTP. Putting the whole app on Cloudflare
would mean rewriting the backend, not reconfiguring it.

`scripts/build_static.py` writes `dist/`, renaming the bundle to `index.html`
and baking the API's URL into the page as `window.COMPASS_API_BASE`. Without
that the page would default to its own origin and look for an API on Cloudflare,
where there is none.

In the Cloudflare project settings:

| Setting | Value |
|---|---|
| Build command | `python3 scripts/build_static.py` |
| Deploy command | `npx wrangler deploy` |
| Environment variable | `API_BASE_URL=https://<your-api-host>/api` |

Because the page and the API are now on different origins, the API must allow
the frontend's origin. Set `FRONTEND_ORIGIN` on the API host — it accepts a
comma-separated list, and the apex and `www` are different origins to a browser:

    FRONTEND_ORIGIN=https://flightplans.cc,https://www.flightplans.cc

## Publishing to GitHub Pages

`.github/workflows/pages.yml` publishes the planner on every push to `main`, at
`https://<owner>.github.io/<repo>/`. Two things need doing once:

1. **Settings → Pages → Source: GitHub Actions.** Without this the workflow runs
   and the deploy step fails — Pages will not accept an artifact until a source
   is chosen.
2. **Allow the Pages origin on the API.** Pages serves static files only, so the
   API stays where it is and the page calls it cross-origin. Add the Pages URL
   to `FRONTEND_ORIGIN` on the API host, alongside any other frontends:

       FRONTEND_ORIGIN=https://oninelol.github.io,https://flightplans.cc

To point Pages at a different backend, set a repository variable `API_BASE_URL`
(Settings → Secrets and variables → Actions → Variables) rather than editing the
workflow. Re-publish without a commit from the Actions tab via "Run workflow".
