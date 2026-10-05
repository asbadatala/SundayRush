# P1 Implementation Plan — Fantasy Football Game-Day Companion

## Context

P0 is committed on branch `p0-mvp` (see `p0_mvp_plan.md` and `DECISIONS.md`). What exists today:

- Yahoo import code, custom teams, a canonical player catalog, Sleeper/ESPN NFL data, a league-specific scoring engine, the game-day dashboard, matchups, anonymous sessions, a fixture mode, and 69 pytest + 14 Playwright tests.

**Yahoo is deferred out of P1.** Yahoo now requires a reviewed application before the Fantasy Sports API returns data. Every data call returns `403 "This application is not authorized"` until approval, and an application is submitted. The P0 Yahoo code stays in the repo, but it's hidden from users in P1 (Phase 0). Yahoo comes back as its own phase once access is approved (see "Deferred: Yahoo" below).

P1 delivers spec §6 without Yahoo:
- Sleeper import and ESPN public-league import.
- Standings, injuries, and projections.
- Google sign-in with cross-device sync.
- Screenshot roster import.

Spec §6 doesn't list these, but P1 depends on them:
- **K/DEF scoring.** Sleeper and ESPN matchup totals include kickers and defenses.
- **Position-scoped scoring rules.** Needed for TE premium.
- **Week navigation.**
- **Hosting on Vercel.**

---

## Decisions (2026-10-04)

| # | Decision | Status |
|---|---|---|
| D1 | **ESPN: public leagues only.** Private leagues return `PRIVATE_LEAGUE_UNSUPPORTED` and point users to Custom Team. Cookie-based private access is deferred. | Decided |
| D2 | **Sign-in: Google only**, implemented in FastAPI on top of the existing session (see Phase 7 for why not Auth.js). Anonymous mode stays available, so a Google account is never required to use the app. | Decided |
| D3 | **Hosting: Vercel** for both the web app and the API, with managed Postgres from the Vercel Marketplace. Details in Phase 6. | Decided |
| D4 | **Screenshot model: a small vision-capable OpenAI (ChatGPT) model** through the OpenAI API with Structured Outputs. The model name is a config value (`OPENAI_MODEL`), chosen from OpenAI's current lineup when Phase 8 starts. | Decided |
| D5 | **Yahoo: deferred out of P1.** | Decided |
| D6 | **Fleaflicker: deferred to P2.** | Decided |

These are recorded as ADR-012 through ADR-017 in `DECISIONS.md`.

**Other suggestions on sign-in:**
- If many users are on iPhones, add **Sign in with Apple** later. It needs a paid Apple Developer account, which is why it isn't in P1.
- An **email magic link** is the usual fallback for people without Google. It needs a transactional email provider (e.g., Resend), so it's deferred too.
- The identity table below supports adding either one without schema changes.

---

## Cross-cutting design

- **Provider adapters:** Sleeper and ESPN implement the existing `FantasyProviderAdapter` Protocol and return only `Normalized*` types. `providers/sync.py` (import, select team, refresh, TTLs, inline `league_errors`) is already provider-agnostic, so each provider needs an adapter, a discover endpoint, and a selection screen.
- **Connections:** neither Sleeper nor ESPN public needs credentials. `ProviderConnection.external_account_identifier` stores the Sleeper user_id, and ESPN needs no connection row.
- **Normalized types added:** `NormalizedStanding`, `NormalizedInjury`, and `NormalizedProjection` (projected *stats*, so each league's rules apply).
- **Projections vs. actuals:** separate tables and API fields (`points` vs. `projected_points`), never summed together, and always labeled "proj" in the UI.
- **Scoring engine extensions (still pure functions):**
  - Position-scoped keys (`reception@TE`).
  - K scoring by FG distance.
  - DEF scoring by tiered points-allowed and yards-allowed rules, stored as rule tables, not code.
- **Rate limits and etiquette:** Sleeper asks to stay under 1,000 calls/minute and to call `/players/nfl` at most once a day. Every provider client reuses the Yahoo client's retry/backoff and latency logging.
- **Serverless-safe by default (needed for Vercel):** no in-process background work, no reliance on local disk, and no per-process state that must be shared, like in-memory rate-limit counters (see Phase 6).

---

## Phases

### Phase 0 — Housekeeping
- Add a `YAHOO_ENABLED` setting, default `false`:
  - When off, Yahoo shows as "Coming soon" on `/teams/new`, like Sleeper/ESPN today.
  - The Yahoo routes return `PROVIDER_UNAVAILABLE`.
  - Yahoo tests still run with the flag on.
- Week navigation: previous/next week on Games and Matchups. The backend already accepts `season`/`week`.
- **Deliverable:** users only see providers that work.

### Phase 1 — Scoring engine: K, DEF, position-scoped rules
- `scoring/engine.py`:
  - Keep `Σ stats × rules` for flat keys.
  - Add tiered rules and position-scoped keys.
  - Remove `UNSCORED_POSITIONS` once K/DEF are covered.
- `stat_keys.py`: map Sleeper's FG-by-distance and team-defense fields, which Sleeper already supplies.
- Extend the spec §14 test cases with K, DEF, and TE-premium.
- **Deliverable:** the engine scores every rostered position, with fixture-tested tiers.

### Phase 2 — Sleeper import (spec §10.4)
- `providers/sleeper/client.py` + `adapter.py`, using the public API (no auth):
  - `GET /v1/user/{username}` → user_id
  - `/v1/user/{user_id}/leagues/nfl/{season}`
  - `/v1/league/{id}` (`scoring_settings`)
  - `/v1/league/{id}/users`
  - `/v1/league/{id}/rosters` (`starters`, `players`, `reserve`, `taxi`, `owner_id`)
  - `/v1/league/{id}/matchups/{week}` (`matchup_id`, `points`, `starters`)
- **Mapping:**
  - Sleeper player ids are our `sleeper_id`, so resolution is exact.
  - `scoring_settings` reuses `stat_keys.py`. Bonus keys (`bonus_rec_te`, …) become position-scoped rules where possible; the rest go to `unsupported_json`.
  - `reserve` → IR, `taxi` → bench.
- Pre-select the user's team by matching `owner_id` to the discovered user_id.
- Matchup totals use Sleeper's reported `points` (authoritative, like ADR-008). Gaps over 0.5 from our engine are logged.
- **Endpoints:** `POST /api/providers/sleeper/discover {username}`. Import, select-team, and refresh go through the existing `/api/leagues/*` with `provider: "sleeper"`.
- **Web:** enable Sleeper on `/teams/new`, and add `/teams/sleeper/select` (username → leagues → confirm team).
- **Deliverable:** a real Sleeper league imports end to end and shows on Games and Matchups next to custom teams. Engine totals match Sleeper's within 0.5.

### Phase 3 — Standings (spec §6)
- Add an optional `get_standings` to the adapter Protocol. Sleeper fills it from roster `settings` (`wins`, `losses`, `ties`, `fpts`, `fpts_against`). ESPN's is added in Phase 5.
- Store standings in a `fantasy_standing` snapshot table (league, season, week, team, rank, W/L/T, PF, PA), refreshed with the league TTL.
- Add `GET /api/leagues/{id}/standings`.
- Web: new `/leagues/[id]` route with Standings and Teams, with the user's team labeled (not color alone). League cards on `/teams` link to it.
- **Deliverable:** every imported league has a standings view.

### Phase 4 — Injuries and projections
- **Injuries:**
  - Normalize to `healthy, questionable, doubtful, out, IR, PUP, suspended` through one code table (`Q`, `D`, `O`, `IR`, `PUP-R`, `SUSP`, `NA`, …).
  - Sources by priority:
    1. The provider roster status (league TTL).
    2. The Sleeper catalog (daily).
    3. A game-day feed for late inactives (evaluate ESPN's team injury data). Refresh it every 30 min on game day, behind `NFLDataProvider`.
  - Show a text badge on rows, with Out/IR starters called out at the top of their game card.
- **Projections:**
  - Use Sleeper's weekly projected stats (unofficial, same caveats as ADR-002) behind `NFLDataProvider.get_projections`, stored in `player_week_projection`.
  - Projected points are computed per league by the same engine.
  - The provider's own team projection, where supplied, wins on matchup cards.
- **Deliverable:** rows show injury status and "proj X.X". Matchup cards show projected totals.

### Phase 5 — ESPN public-league import (spec §10.5, D1)
- `providers/espn/`, using ESPN's fantasy read API:
  - `lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}/segments/0/leagues/{id}`
  - views: `mTeam`, `mRoster`, `mMatchup`, `mSettings`, `mStandings`
- Discovery by league ID: `POST /api/providers/espn/discover {league_id, season}`. The UI explains where to find the ID in the ESPN league URL.
- ESPN stat ids map to normalized keys in `providers/espn/stat_map.py`, verified against recorded fixtures.
- The user always confirms their team: public access has no "current login."
- A 401/403 from ESPN means the league is private, so return `PRIVATE_LEAGUE_UNSUPPORTED` with: "This ESPN league is private. Ask your commissioner to make it viewable to the public, or create the roster as a custom team."
- **Deliverable:** a public ESPN league imports end to end, with standings. Private leagues fail with that message.

### Phase 6 — Deployment on Vercel (D3; going live still needs the owner's go-ahead)

**Topology: two Vercel projects from this monorepo, same origin for the browser.**

| Project | Root dir | What it runs |
|---|---|---|
| `sundayrush-web` | `apps/web` | Next.js. Owns the custom domain (e.g. `sundayrush.app`). |
| `sundayrush-api` | `apps/api` | FastAPI on Vercel's Python runtime (serverless functions). |

- The web project's existing `rewrites` proxy `/api/*` to the API project's URL (`API_URL`, set at build time). The browser still only talks to the web domain, so the session cookie, OAuth callbacks, and secrets work exactly as they do locally. No CORS needed.
- We use two projects rather than putting Python functions inside the Next project because it avoids `/api` route collisions with Next, keeps the Python bundle separate, and matches today's code with no restructuring.

**Database:**
- Postgres from the Vercel Marketplace (**Neon recommended**). It supports `pg_trgm`, and its Vercel integration can create a **database branch per preview deployment**, so previews never touch production data.
- Serverless functions open many short-lived connections, so:
  - Use Neon's **pooled** connection string.
  - Create the SQLAlchemy engine with `NullPool` when `SERVERLESS=1`.
  - Turn off psycopg prepared statements (`prepare_threshold=None`), as PgBouncer transaction pooling requires.
- Pin the API function region next to the database region (e.g. `iad1` with Neon us-east).

**Migrations:** functions can't run migrations on boot like the Dockerfile does. A GitHub Action runs `alembic upgrade head` against production on merge to `main`, before Vercel promotes the deploy. Preview branches migrate their own Neon branch.

**Code changes needed for serverless:**
1. **Rate limiting.** slowapi's in-memory counters reset per function instance, so they don't actually limit anything. Back them with shared storage: Upstash Redis from the Vercel Marketplace (free tier, slowapi supports a `storage_uri`), or a small Postgres counter table. **Recommendation: Upstash.** Per ADR-007, the `Cache` interface can move to Redis at the same time if needed; `DbCache` keeps working either way.
2. **Daily player-catalog sync.** Move it out of user requests into a **Vercel Cron Job** calling `POST /api/internal/sync-players`, protected by `Authorization: Bearer $CRON_SECRET`. Hobby-plan crons run at most once a day, which fits. `ensure_players_fresh` stays as a fallback.
3. **Bundle hygiene.** Exclude `tests/` and fixtures from the function bundle (`.vercelignore`). Confirm Vercel installs from `pyproject.toml`/`uv.lock`, or export `requirements.txt` at build time.
4. **Entrypoint.** Point Vercel at `app.main:app`, following Vercel's FastAPI configuration at implementation time.
5. **Production settings.** `FIXTURE_MODE` off (the fixture-only endpoint already 404s). `COOKIE_SECURE=true`, and `WEB_BASE_URL` set to the custom domain.

**Environment variables (Vercel project settings, never in the repo):**
- API: `DATABASE_URL`, `SESSION_SECRET`, `TOKEN_ENCRYPTION_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `CRON_SECRET`, `RATE_LIMIT_STORAGE_URI`, `WEB_BASE_URL`, `SERVERLESS=1`.
- Web: `API_URL`.
- Production and Preview get different secrets.

**Things to know about Vercel:**
- **Plan:** Vercel's Hobby plan is for personal, non-commercial use. Anything commercial (ads, paid tiers, a business) needs **Pro (about $20/month per member)**. Check current terms before launch.
- **Cold starts:** the first request after idle is slower. Game-day polling keeps functions warm during games.
- **Function duration:** keep requests short. The longest today is a first game-day load syncing several leagues, which takes a few seconds and is fine.
- **Logs:** structlog's stdout goes to Vercel logs. Retention is short on Hobby, so add a log drain if we need history.
- **Direct API URL:** the API project's `*.vercel.app` URL is reachable directly. That's harmless, because sessions are scoped to the web domain and every route requires a session, but don't advertise it.

**CI (GitHub Actions):** ruff, mypy, pytest (Postgres service), web lint and build, and Playwright on every PR. Migrations run on merge.

**Docker:** `docker-compose.yml` and the Dockerfiles stay for local development and as a fallback host.

**Deliverable:** production on the custom domain, previews per PR with their own database branch, and CI gating `main`.

### Phase 7 — Google sign-in and cross-device sync (spec §6, D2)
- **Why FastAPI rather than Auth.js:**
  - Our session already lives in FastAPI (`ff_session`).
  - Auth.js would add a second session in Next and need a JWT bridge to the API.
  - Doing Google OIDC in FastAPI (e.g. Authlib) keeps one session model and works unchanged behind the Vercel rewrites.
- **Flow:**
  1. `GET /api/auth/google/start` creates `state` + `nonce` (signed short-lived cookie, like the Yahoo flow) and redirects to Google with scopes `openid email profile`.
  2. `GET /api/auth/google/callback` verifies `state`, the ID token (signature, `aud`, `iss`, `nonce`, `exp`), and `email_verified`.
  3. It then links the identity or signs in, rotates `ff_session`, and redirects to the page the user started from.
- **Google Cloud setup:**
  - Create an OAuth client (Web application) with redirect URIs `https://<domain>/api/auth/google/callback` and `http://localhost:3200/api/auth/google/callback` (Google allows http for localhost).
  - Basic scopes need no sensitive-scope review. Move the consent screen from **Testing** (only listed test users can sign in) to **In production** before launch.
  - Previews: Google needs exact redirect URIs, so sign-in on preview deployments uses one fixed preview domain. Per-PR URLs can't sign in.
- **Data model:** a `user_identity` table (`user_id`, `kind`=`google`, `subject`, `email`, `verified_at`, unique on `kind + subject`). Apple or email can be added later as new `kind`s.
- **Anonymous → account migration:**
  - The device's anonymous user has data and the Google identity is new → attach the identity to that same `User`. Nothing moves.
  - The identity already belongs to another user → merge the anonymous user into it in one transaction:
    - Re-point leagues, teams, connections, and profiles.
    - Duplicate leagues (same provider + external id): keep the account's copy.
    - Delete the anonymous user.
- **Sync:**
  - Display filters move from `localStorage` to `user_preferences` (`GET/PUT /api/preferences`). `localStorage` becomes a cache that seeds a new account once.
  - Notification settings are schema only (notifications are P2).
- **Settings:** sign in/out, the signed-in email, and "Delete account" (cascades like "Clear local data").
- Rate-limit the auth endpoints.
- **Deliverable:** set up on a phone, sign in with Google on a laptop, and see the same leagues, custom teams, and filters.

### Phase 8 — Screenshot roster import (spec §6, D4)
- **Endpoint `POST /api/manual-teams/screenshot`:**
  - Validate type (PNG/JPEG/WebP), size (≤ 4 MB), and that the image decodes. Vercel limits request bodies to about 4.5 MB, so the web app downsizes images in the browser before upload.
  - Process in memory only; no file is written, so there's nothing to clean up (spec §21).
- **Model call:**
  - Use the OpenAI API (Responses API) with the image, a short instruction, and a **Structured Outputs JSON schema** matching spec §6 (`team_name`, `starters[]`, `bench[]` with `name` + `position`). The model name comes from `OPENAI_MODEL`.
  - `OPENAI_API_KEY` stays server-side, and the image is never logged.
- **Limits:** a per-session rate limit and a daily spend cap (count calls, reject when over), so a public endpoint can't run up the OpenAI bill.
- **Resolution:**
  - Each name runs through `PlayerResolver` in a new **candidates** mode that returns the top 3 matches with confidence.
  - Abbreviations ("J. Allen") are narrowed by position and team.
  - Nothing below threshold is auto-selected (spec §20).
- **Web:** on `/teams/custom/new`, "Import from screenshot" → upload → confirmation list (confident rows pre-selected, ambiguous rows require a choice) → the existing builder → save.
- **Tests:** fixture images with recorded model responses (no live OpenAI calls in CI), plus resolver tests for abbreviated and ambiguous names.
- **Privacy note for the Settings page:** screenshots are sent to OpenAI for extraction. Per OpenAI's API data policy at the time of writing, API inputs aren't used for training by default. Re-check it when building.
- **Deliverable:** a real roster screenshot becomes a confirmed custom team in under a minute.

---

## Deferred: Yahoo (returns when access is approved)

Already built in P0. Remaining work, as its own phase when Yahoo approves:

- Set `YAHOO_ENABLED=true`, and add the required attribution ("Fantasy data provided by Yahoo Fantasy," with logo and link) wherever Yahoo data appears.
- Register a **separate production Yahoo app** with redirect URI `https://<domain>/api/providers/yahoo/auth/callback`, and add its keys to the Vercel API project.
- Run a real-league check. Record real fixtures with `scripts/capture_fixtures.py yahoo` (names scrubbed), and confirm `stat_map.py` against real settings, including the K/DEF stat_ids mapped in Phase 1.
- Add Yahoo standings (`league/{key}/standings`).

---

## Testing & verification

- **Unit:**
  - Engine K/DEF/tier/position-scoped cases.
  - Sleeper and ESPN parsers and stat maps against recorded fixtures.
  - Injury normalization.
  - Projections kept separate from actuals.
  - Account merge rules.
  - Google ID-token validation (bad `aud`/`iss`/`nonce`/expired).
  - Resolver candidates mode.
- **Integration:**
  - Sleeper discover → import → select → matchups → game-day.
  - ESPN public import, and private → `PRIVATE_LEAGUE_UNSUPPORTED`.
  - Standings.
  - Google sign-in with merge conflicts (mocked Google endpoints via respx).
  - The cron endpoint rejects a missing or wrong `CRON_SECRET`.
  - Screenshot validation rejects oversized, wrong-type, and corrupt files.
- **E2E (Playwright, `FIXTURE_MODE`, mobile + desktop):**
  - Sleeper import.
  - ESPN private-league message.
  - Standings.
  - Injury badge and projections.
  - Sign in from two browser contexts and confirm the data matches (fake Google in fixture mode, like the fake Yahoo OAuth).
  - Screenshot import confirmation.
- **Deployment smoke test:** after the first preview deploy, run the Playwright suite against the preview URL with fixture mode off, using read-only checks only.
- **Real-data checks:** one live Sleeper league and one public ESPN league compared against the provider's own app on a real Sunday before calling those phases done.

## P1 acceptance criteria

- Real Sleeper leagues and public ESPN leagues import end to end alongside custom teams.
- Engine totals match provider-reported totals within 0.5, including K and DEF.
- Every imported league has standings. Rows show injury status and projections, separate from actual points.
- Private ESPN leagues fail with an actionable message.
- A user can sign in with Google, and their configuration follows them to a second device. Anonymous data merges without loss or duplicates. The app stays fully usable without signing in.
- A roster screenshot becomes a confirmed custom team, and low-confidence matches always require confirmation.
- Production runs on Vercel at a custom domain, with per-PR previews on isolated database branches, CI gating `main`, and secrets server-side only.

## Out of scope for P1

- Yahoo (see above).
- ESPN private leagues.
- Sign-in methods other than Google.
- Fleaflicker (deferred to P2; it will use the same adapter pattern).
- Spec §7 P2 items and §8 non-goals.
- Owner wishlist items (spec §30): broader AI features, betting mode, sports bar finder, "What Matters Right Now?". Each needs its own design pass; betting mode also needs legal, geographic, and age-verification research. Research and scoping live in `wishlist.md`.

## Open risks

- **Unofficial endpoints:** Sleeper stats/projections, ESPN's fantasy API, and ESPN's scoreboard can change without notice. They sit behind interfaces, and fixtures catch shape changes.
- **ESPN public-only** covers fewer users than ESPN overall, since many ESPN leagues are private by default. Measure how often `PRIVATE_LEAGUE_UNSUPPORTED` fires before deciding whether to revisit cookie support.
- **Serverless limits:** cold starts, connection limits (mitigated by pooling + `NullPool`), the 4.5 MB request body cap (mitigated by client-side image resizing), and cron frequency on Hobby.
- **Vercel plan terms:** commercial use requires Pro.
- **Google consent screen:** must be moved to "In production," or only test users can sign in.
- **OpenAI cost and accuracy:** mitigated by the confirmation UI, rate limits, and the spend cap.
