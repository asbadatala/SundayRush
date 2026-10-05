# SundayRush

SundayRush is a cross-platform fantasy football game-day dashboard. It brings all your leagues, players, live scores, and matchups into one view, organized around the NFL games you're watching.

P0 includes Yahoo import, custom (manual) teams, canonical NFL players, live schedule and stats, league-specific scoring, a game-day dashboard, and matchups. It works without an account (anonymous-first) and is designed for phones first.

```
apps/api   FastAPI + SQLModel + Alembic (Python 3.12, uv)
apps/web   Next.js 16 + Tailwind + shadcn/ui + TanStack Query
e2e        Playwright (FIXTURE_MODE full-stack tests)
```

Architecture decisions are recorded in [DECISIONS.md](DECISIONS.md), the product spec is [fantasy_football_mvp_spec.md](fantasy_football_mvp_spec.md), and the build plan is [p0_mvp_plan.md](p0_mvp_plan.md).

## Run locally

Prerequisites: Docker, uv, Node 20+, and pnpm.

```bash
cp .env.example .env                 # fill in SESSION_SECRET and TOKEN_ENCRYPTION_KEY
docker compose up -d db              # Postgres 16 on localhost:5442

cd apps/api
uv sync
uv run alembic upgrade head
uv run python -m app.nfl_data.sync_players --week   # player catalog + current week (optional; also lazy)
uv run fastapi dev app/main.py --port 8000          # http://localhost:8000/api/health

cd ../web
pnpm install
pnpm dev --experimental-https        # https://localhost:3000 (proxies /api/* to :8000)
```

Plain `pnpm dev` (http) also works for custom teams. In that case, set `COOKIE_SECURE=false` in `.env` so the session cookie is accepted over http.

### Offline demo / fixture mode

To run with no Yahoo app and no network, start the API with `FIXTURE_MODE=1 COOKIE_SECURE=false`. This serves recorded Week 4 2026 NFL data and a fake Yahoo OAuth with two sample leagues.

## Connecting Yahoo (one-time setup)

1. Create an app at https://developer.yahoo.com/apps/create/:
   - **API permissions:** Fantasy Sports → Read.
   - **Redirect URI:** `https://localhost:3000/api/providers/yahoo/auth/callback`.
2. Put `YAHOO_CLIENT_ID` and `YAHOO_CLIENT_SECRET` in `.env`, then run the web app with `pnpm dev --experimental-https`.
3. If Yahoo rejects `localhost`, start a tunnel (`cloudflared tunnel --url https://localhost:3000` or ngrok). Use the tunnel URL for the redirect URI, `YAHOO_REDIRECT_URI`, and `WEB_BASE_URL`.

## Tests

```bash
cd apps/api && uv run pytest              # unit + integration (needs `docker compose up -d db`)
cd apps/api && uv run ruff check . && uv run mypy app
cd apps/web && pnpm lint && pnpm build
cd e2e && pnpm install && npx playwright install chromium && pnpm test   # boots API + web itself
```

- Integration tests use the `sundayrush_test` database.
- E2E uses `sundayrush_e2e`, which is rebuilt on every run, and covers spec §23 UI flows 1–9 at mobile and desktop viewports.
- No test touches live services.
- To re-record fixtures:
  - NFL: `uv run python -m scripts.capture_fixtures nfl --season 2026 --week 4`
  - Yahoo (with a connected user, names scrubbed): `... yahoo --user-id <id> --league <key> --week <n>`
