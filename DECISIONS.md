# Architecture Decision Log

Short ADRs for the decisions spec §29 asks us to record. Newest decisions go at the bottom; superseded ones are marked, never deleted.

---

## ADR-001 — Stack: Next.js + FastAPI + Postgres

**Status:** accepted (P0)

- **Web:** Next.js 16 (App Router, TypeScript), Tailwind v4, shadcn/ui (Base UI primitives), TanStack Query.
- **API:** FastAPI on Python 3.12, managed with uv. SQLModel/SQLAlchemy, Alembic, httpx, structlog, slowapi.
- **DB:** PostgreSQL 16, which also provides `pg_trgm` for player search.

**Why:** the spec's preferred architecture. Python fits the data-normalization work (Yahoo's JSON shapes, stat mapping, fuzzy matching). The provider, NFL-data, scoring, and game-day boundaries are Python packages, not network services.

**Same origin:** Next.js `rewrites` proxy `/api/*` to FastAPI. The browser only ever talks to Next, so the session cookie and the Yahoo OAuth callback live on one origin, and provider secrets stay in FastAPI.

## ADR-002 — NFL data: Sleeper + ESPN public JSON behind `NFLDataProvider`

**Status:** accepted for P0. Re-evaluate before any paid or public launch.

| Need | Source | Notes |
|---|---|---|
| Player catalog + cross-IDs | Sleeper `GET /v1/players/nfl` | Includes `yahoo_id`, `espn_id`, `gsis_id`, `sportradar_id`. About 5 MB, so we refresh at most once a day. |
| Current week | Sleeper `GET /v1/state/nfl` | Uses `display_week`. |
| Raw weekly stats | Sleeper `api.sleeper.com/stats/nfl/{season}/{week}` | Per player per week. We normalize to our own keys and never use Sleeper's precomputed `pts_*`. |
| Schedule, status, score, clock, network | ESPN `site.api.espn.com/.../nfl/scoreboard?dates=&seasontype=2&week=` | |

Evaluation against spec §13:
- **Licensing:** neither source is an officially licensed, documented public API. Both are unauthenticated public JSON used by many hobby projects. That's acceptable for a P0 prototype, but not as the long-term commercial source.
- **Limits:** no published limits. We poll at most once every 60 s while games are live and hourly otherwise, behind a cache.
- **Latency:** Sleeper stats update within about a minute during games. ESPN scoreboard updates within seconds.
- **ID quality:** Sleeper carries `yahoo_id` for about 55% of skill-position players, mostly veterans. The rest resolve by exact name + team + position (see ADR-005).
- **Coverage:** full regular-season schedule and offensive stats. K and DEF stats exist, but K/DEF *scoring* is deferred.
- **Price:** free.

**Consequences:** everything sits behind `app/nfl_data/base.py::NFLDataProvider`, so a licensed feed (Sportradar, SportsDataIO, nflverse) can replace it in one module. Team codes are canonicalized to Sleeper's (`WAS`, `LAR`, `JAX`); ESPN's `WSH` maps to `WAS`.

**Deviation from spec:** these sources publish stats per week, not per game. `get_week_stats(season, week)` replaces `getPlayerGameStats(gameId)`, and stats join to games through the player's NFL team.

## ADR-003 — Production database: managed Postgres

**Status:** accepted. Any managed Postgres 14+ with `pg_trgm` works (Neon, Render, Fly, RDS). The schema lives in Alembic migrations under `apps/api/alembic/versions`.

## ADR-004 — Anonymous sessions and Yahoo token storage

**Status:** accepted (P0)

- The first request gets an `ff_session` cookie: HTTP-only, `Secure` in production, `SameSite=Lax`, 400-day lifetime. It holds an opaque user id signed with `itsdangerous`.
- An anonymous `User` row is created lazily for that id. Every query is scoped by `user_id`, and external provider ids are never treated as authorization.
- The web client calls `GET /api/session` once before anything else, so parallel first-load requests don't mint separate users.
- Leagues, teams, and tokens are stored server-side. Only display filters live in `localStorage`.
- **Yahoo tokens:** encrypted at rest with Fernet (`TOKEN_ENCRYPTION_KEY`) in `provider_connection`, together with `token_expires_at` and scopes. Tokens are never sent to the browser or logged; a structlog processor redacts token-like keys.
- **OAuth state:** a random `state` is stored in a short-lived (10 min) signed `ff_oauth_state` cookie and checked on callback.
- **Refresh:** the access token refreshes about 5 minutes before expiry, plus a forced refresh on any Yahoo 401. A rejected refresh raises `PROVIDER_AUTH_EXPIRED`, which the UI shows as a "Reconnect Yahoo" banner.
- **Disconnect:** "Disconnect Yahoo" deletes the connection row. "Clear local data" deletes the anonymous user, and everything it owns cascades.
- **P1 accounts:** attach an email/identity to the existing `User` row so anonymous data migrates in place.

## ADR-005 — Canonical player id

**Status:** accepted

`canonical_player.id` is our own integer and is never a provider id. The Sleeper catalog seeds it and carries cross-ids. Resolution order (spec §20):

1. `player_id_mapping`
2. provider-id column (`yahoo_id`)
3. exact normalized name + team + position, then unique name + position across teams (for trades)
4. `rapidfuzz` ratio ≥ 0.92, logged

Team defenses resolve by NFL team. Results are written to `player_id_mapping`, so we never fuzzy-match the same player twice. Unresolved players are stored with their provider name and render as "unmapped" rows; they're never hidden.

## ADR-006 — Polling, not push (no worker in v1)

**Status:** accepted (P0)

Freshness is checked on read:
- NFL schedule/stats TTL is 60 s while any game is live or within 15 min of kickoff, otherwise 1 h.
- League roster/matchup TTL is 5 min on game day, otherwise 1 h.
- The player catalog refreshes at most once a day, and re-joins stats for weeks loaded before it.
- "Refresh" bypasses all TTLs.

The web app polls `/api/game-day` every 60 s only while a game is live. The future path (spec §17): a worker writes stat deltas, then pushes SSE to clients.

## ADR-007 — No Redis in v1

**Status:** accepted

Caching goes through `app/cache/base.py::Cache`, implemented by a Postgres TTL table (`cache_entry`) that mostly stores freshness markers. The normalized data itself lives in real tables. Add a Redis `Cache` implementation when live polling volume or multi-instance fan-out requires it.

## ADR-008 — Scoring

**Status:** accepted

- The engine is a pure function: `Σ stats[key] × rules[key]` over canonical, non-overlapping normalized keys, rounded to 2 decimals.
- Presets (Standard, Half PPR, Full PPR) match Yahoo defaults: INT −1, fumble lost −2.
- Yahoo `stat_id`s map through `providers/yahoo/stat_map.py`. Unmapped stats, yardage bonuses, and K/DEF categories are saved in `scoring_profile.unsupported_json` instead of being silently dropped.
- K/DEF rows show "points unavailable".
- **Matchup totals use Yahoo's reported `team_points`**, which are authoritative. Gaps over 0.5 between Yahoo's total and the engine's sum are logged.

## ADR-009 — Deployment topology

**Status:** proposed. We will not deploy until the owner gives the go-ahead.

- **Web:** Vercel. Set `API_URL` to the API's internal or public URL at build time, because rewrites are resolved during the build.
- **API:** Render or Fly (`apps/api/Dockerfile`). Migrations run on boot.
- **DB:** managed Postgres.

The browser stays same-origin through the Next rewrites. The Yahoo redirect URI is `https://<web-host>/api/providers/yahoo/auth/callback`. Required secrets: `SESSION_SECRET`, `TOKEN_ENCRYPTION_KEY`, `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET`.

## ADR-010 — ESPN authentication (P1)

**Status:** open. Not needed for P0. Research the read-only league-ID path first. If private leagues need `espn_s2`/`SWID` cookies, isolate them inside `providers/espn/`, or return `PRIVATE_LEAGUE_UNSUPPORTED` and point the user to Custom Team.

## ADR-011 — Account/authentication provider (P1)

**Status:** superseded by ADR-013.

## ADR-012 — ESPN: public leagues only in P1

**Status:** accepted (2026-10-04). ESPN import supports leagues viewable to the public, discovered by league ID. When ESPN returns 401/403, the app returns `PRIVATE_LEAGUE_UNSUPPORTED` and points the user to Custom Team. Cookie-based (`espn_s2`/`SWID`) private access is deferred. Resolves ADR-010 for P1.

## ADR-013 — Sign-in: Google, implemented in FastAPI

**Status:** accepted (2026-10-04).

- Google OIDC (`openid email profile`) runs in FastAPI on top of the existing `ff_session` model. A `user_identity` row links a Google subject to a `User`.
- **Why not Auth.js:** it would add a second session in Next.js plus a JWT bridge to the API.
- Anonymous use stays fully supported.
- Apple sign-in and email magic links are possible later additions as new identity kinds.

## ADR-014 — Hosting: Vercel (supersedes ADR-009)

**Status:** accepted (2026-10-04). Deploying still needs the owner's go-ahead.

- **Projects:** two Vercel projects. `apps/web` runs Next.js and owns the domain. `apps/api` runs FastAPI on Vercel's Python runtime.
- **Same origin:** the browser stays same-origin through the existing Next rewrites.
- **Database:** Postgres from the Vercel Marketplace (Neon, pooled connection, `NullPool`, branch per preview).
- **Serverless:**
  - Migrations run from CI, not on boot.
  - The daily player sync runs as a Vercel Cron Job.
  - Rate limiting moves to shared storage (Upstash Redis).
- See `p1_plan.md` Phase 6.

## ADR-015 — Screenshot extraction: OpenAI vision model

**Status:** accepted (2026-10-04).

- **Model:** a small vision-capable OpenAI model through the OpenAI API with Structured Outputs. The model is configured by `OPENAI_MODEL`.
- **Images:** processed in memory and never stored or logged.
- **Limits:** per-session rate limits and a daily spend cap.
- **Resolution:** the canonical player resolver produces candidates, and the user confirms every match below the confidence threshold.

## ADR-016 — Yahoo deferred out of P1

**Status:** accepted (2026-10-04).

- **Why:** Yahoo Fantasy Sports API access now requires Yahoo's application approval (pending). Until then, data calls return 403.
- **In P1:** the P0 Yahoo code stays, but it's hidden behind `YAHOO_ENABLED=false`.
- **When approved:** Yahoo returns with attribution, a separate production Yahoo app, and a real-league check.

## ADR-017 — Fleaflicker deferred to P2

**Status:** accepted (2026-10-04). P1 ships Sleeper and ESPN public leagues. When Fleaflicker comes in P2, it will be another `FantasyProviderAdapter` built on its public API (`FetchUserLeagues`, `FetchLeagueRosters`, `FetchLeagueScoreboard`, `FetchLeagueRules`, `FetchLeagueStandings`).
