# Deployment: one shared database, many devices

The app runs on any device once three pieces are reachable over the internet: Supabase (PostgreSQL
with pgvector, plus Supabase Auth for sign-in), the FastAPI backend, and the static React frontend.
Supabase is the only stateful piece; the other two are stateless and can be redeployed freely.

**Division of labour:** Supabase Auth handles *who you are* (sign-up, email confirmation, login,
password reset, sessions). Our backend handles *what you may do*: it verifies the Supabase token,
then reads your role and department from its own `users` table on every request.

```
browser / phone ──▶ frontend (static) ──▶ Supabase Auth (login)
                       │
                       └─ Bearer token ──▶ backend (FastAPI) ──▶ Supabase Postgres + pgvector
```

## 1. Database: Supabase

1. Create a Supabase project (pick a region near your backend host) and note the database password.
2. **Turn off the Data API** (Project Settings → Data API). We only use Supabase as Postgres; all
   access control lives in FastAPI. As a second line of defence, migration `20260929_0003`
   enables row-level security on every table, so even with the API on, the public `anon` key sees
   nothing.
3. Project → **Connect** → copy two connection strings:
   - **Transaction pooler** (host `aws-0-<region>.pooler.supabase.com`, port `6543`) → `DATABASE_URL`
     for the running app.
   - **Session pooler** (same host, port `5432`) → `MIGRATION_DATABASE_URL` for Alembic. Do not use
     the "Direct connection" (`db.<ref>.supabase.co`): it is IPv6-only unless you buy the IPv4 add-on,
     and most home/campus networks and hosts cannot reach it.
   The user name looks like `postgres.<project-ref>` on the poolers. URL-encode special characters
   in the password (`#` → `%23`, `@` → `%40`).
4. pgvector: the first migration runs `CREATE EXTENSION vector` itself. If it is refused, enable
   **vector** under Database → Extensions and rerun.

No URL editing is needed: the backend accepts the strings as pasted and converts them for asyncpg
(`app/core/config.py::normalise_async_url`): it adds `ssl=require` for Supabase hosts and turns
off prepared-statement caching on pooled hosts, which the transaction pooler cannot support.

**Free-tier caveat:** Supabase pauses free projects after about a week of inactivity, and you
restore them manually from the dashboard. Open the app (or the dashboard) shortly before any review
or demo, or upgrade for the demo period. `GET /api/v1/health` reports `database: disconnected`
when the project is paused.

**Tests never touch the hosted database.** The suite drops and rebuilds its schema, so it runs
against local Docker Postgres (`fixmycampus_test`) and refuses any database whose name lacks "test".

### Auth settings (Supabase dashboard)

1. **Authentication → URL Configuration:** set **Site URL** to your frontend address
   (`http://localhost:5173` while developing) and add every frontend address you use
   (`http://localhost:5173/**`, your deployed URL) under **Redirect URLs**. Confirmation and
   password-reset emails link back to these.
2. **Authentication → Sign In / Providers → Email:** keep **Confirm email** on. Free-tier email is
   throttled to a few messages an hour, so create demo accounts ahead of a review (the admin page and
   `seed_demo_users.py` create pre-confirmed accounts that send no email).
3. **Authentication → Hooks → Before User Created:** restricts sign-up to `@mvsrec.edu.in` at the source,
   so nobody can bypass the website and sign up with another address. Run
   `docs/supabase/restrict_signup_domain.sql` once in **SQL Editor** (already done for this project),
   then in the dashboard choose **Add hook → Postgres function → `public.hook_restrict_signup_domain`**
   and save. If you change the allowed domain, edit it in that SQL file, the backend
   (`ALLOWED_EMAIL_DOMAINS`) and the frontend (`VITE_ALLOWED_EMAIL_DOMAIN`).
4. **Project Settings → API Keys:** copy the **anon / publishable** key (public; goes in
   `frontend/.env`) and the **secret / service_role** key (server-only; goes in `backend/.env` as
   `SUPABASE_SERVICE_ROLE_KEY`). Never put the secret key in the frontend or commit it.

## 2. First-time database setup

Run these once, from `backend/`, with the Supabase values in your environment (or in `.env`):

```bash
export DATABASE_URL="postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres"
export MIGRATION_DATABASE_URL="postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres"

alembic upgrade head              # schema, pgvector, ticket-number sequence, RLS, profile table
python scripts/seed_database.py   # roles, departments, categories, SLA rules
```

**First admin:** open the app, register, click the confirmation link, and sign in once (this creates
your profile as a student). Then promote yourself - no password is involved:

```bash
python scripts/create_admin.py --email you@campus.edu --name "Your Name"
```

Reload the app and the Admin page appears. From there use **Admin → User Management** to create
coordinator and staff accounts (they are created pre-confirmed with a password you set; staff must
be given a department). Optional: `python scripts/seed_demo_users.py --yes` creates one working
login per role for demos; it prints a generated password once. Delete those accounts before real use.

## 3. Backend host (Render, Railway, Fly.io, …)

Build from `docker/backend/Dockerfile` with the **repository root** as the build context. Set:

| Variable | Value |
| --- | --- |
| `ENVIRONMENT` | `production` (the app refuses to boot without `SUPABASE_URL`) |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | the **secret / service_role** key (server-side only) |
| `DATABASE_URL` | Supabase **transaction pooler** URL (port 6543) |
| `MIGRATION_DATABASE_URL` | Supabase **session pooler** URL (port 5432; used by `alembic upgrade head` only) |
| `BACKEND_CORS_ORIGINS` | your frontend origin(s), comma separated, e.g. `https://fixmycampus.vercel.app` |
| `DEBUG` | `False` |

Run `alembic upgrade head` as the release/pre-deploy command so schema changes ship with the code.
The container listens on `$PORT` (default 8000). Health check: `GET /api/v1/health`.

## 4. Frontend host (Vercel, Netlify, Cloudflare Pages, …)

```bash
cd frontend
VITE_API_BASE_URL="https://<your-backend-host>/api/v1" \
VITE_SUPABASE_URL="https://<project-ref>.supabase.co" \
VITE_SUPABASE_ANON_KEY="<anon / publishable key>" \
npm run build   # outputs dist/
```

Deploy `dist/` as a static site with an SPA fallback (every path serves `index.html`), so
`/tickets/TICK-…` survives a refresh. The `VITE_*` values are baked in at build time.

## Run with Docker

| | Command | What you get |
|---|---|---|
| Development | `docker compose up --build` | hot-reload backend (:8000), Vite (:5173), local Postgres (:5432) |
| Production | `docker compose -f docker-compose.prod.yml up -d --build` | nginx on `${HTTP_PORT:-80}` serving the SPA and proxying `/api/` and `/health`, backend, one-shot migration; database is the one in `backend/.env` (Supabase) |
| Local demo | `docker compose -f docker-compose.prod.yml -f docker-compose.localdb.yml up -d --build` | same as production, but with its own pgvector Postgres (database `fixmycampus`, not published on the host) instead of Supabase |

`make dev`, `make prod`, `make prod-local`, `make kb-load`, `make logs` are shortcuts for these.

**Which variables go where**

- `backend/.env`, read at runtime (never baked into an image): `DATABASE_URL`, `MIGRATION_DATABASE_URL`,
  `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`, `BACKEND_CORS_ORIGINS`, and `ENVIRONMENT=production`.
  The browser talks to nginx on the same origin, so CORS only matters if you host the frontend elsewhere.
- `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_ALLOWED_EMAIL_DOMAIN`, read at **build** time (public
  values, they end up in the JS bundle). Export them in the shell or a root `.env` before `up --build`; if they
  are empty, the build uses `frontend/.env`. `VITE_API_BASE_URL` defaults to `/api/v1` (same origin). Changing any
  of them needs a rebuild: `docker compose -f docker-compose.prod.yml build frontend`.

**Knowledge base.** The college pages are not in the image. Load them from `./data` (mounted read-only) after the
stack is up:

```bash
docker compose -f docker-compose.prod.yml --profile tools run --rm kb-load
# prod-local: add -f docker-compose.localdb.yml (the loader then writes to the local database)
```

**Before you go live**

- Supabase dashboard, Authentication, URL Configuration: set **Site URL** to the deployed address and add it
  (and `<address>/**`) to **Redirect URLs**, or confirmation and password-reset links point at the wrong place.
- The container serves plain HTTP. Put HTTPS in front of it (Caddy, or your host's proxy / load balancer) and
  forward to `HTTP_PORT`; nginx keeps the `X-Forwarded-Proto` it receives.
- The backend is a single process on purpose: the auto-close loop and the chatbot rate limit live in memory.
  Do not add `--workers` or run several backend replicas without moving those out first.
- Never run `docker-compose.prod.yml` alone when you only want to try things: it migrates the database in
  `backend/.env`. Use the `localdb` overlay for experiments.

## 5. Running the tests

```bash
docker compose up -d db                # local pgvector Postgres
cd backend && .venv/bin/python -m pytest -q
```

## Security notes

- Never commit `.env` files; they are git-ignored. The anon key is public by design; the
  service-role/secret key is not - if it leaks, rotate it in the Supabase dashboard.
- Roles are never read from the token. They come from our `users` table on every request, so an
  admin's role change or deactivation takes effect immediately. Deactivating also bans the account
  at Supabase so it cannot sign in or refresh again.
- Self-signup can only ever produce STUDENT or FACULTY accounts, whatever the sign-up request claims.
- Sign-up is limited to the college email domain in three layers: the register form, the backend
  (refuses to create a profile for any other domain, so such an account cannot use the app even if it
  exists in Supabase) and the Supabase hook (refuses to create the account at all). Accounts an admin
  creates from the Admin page, and profiles that already exist, are exempt from the backend rule.
- Supabase's login endpoint rate-limits attempts; our own API still has no rate limiting. Add it
  (at the host/proxy or with `slowapi`) before a public launch.
