# P0 MVP Implementation Plan — Fantasy Football Game-Day Companion

## Context

`fantasy_football_mvp_spec.md` defines the product. The folder currently has only the spec (greenfield, no git). P0 means **Yahoo import + custom (manual) teams → canonical players → NFL schedule/live stats → league-specific scoring → game-day dashboard + matchups**, anonymous-first, mobile-first.

Decisions confirmed:
- **Stack:** Next.js (TS, App Router, Tailwind, shadcn/ui, TanStack Query) + FastAPI (Python 3.12, uv, SQLModel, Alembic, httpx) + Postgres. No Redis in v1; caching sits behind an interface.
- **NFL data:** free public JSON, isolated behind `NFLDataProvider`:
  - Sleeper `/v1/players/nfl` for the canonical player catalog. It includes `yahoo_id`, `espn_id`, and `gsis_id`, so Yahoo mapping is mostly exact.
  - Sleeper `/v1/state/nfl` for the current week.
  - Sleeper weekly stats (`api.sleeper.com/stats/nfl/{season}/{week}?season_type=regular`) for raw per-player stats.
  - ESPN `site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard` for games: status, score, clock, broadcasts.
- **Yahoo app:** not registered yet. The plan includes registration and local HTTPS.

Build order differs from spec §25 on purpose. Custom teams + game-day come **before** Yahoo, so the full loop works end-to-end without OAuth, and Yahoo then plugs into a proven pipeline.

---

## Repo layout

```
/apps/web            Next.js app
/apps/api            FastAPI app
  app/
    main.py, config.py, db.py, session.py, logging.py
    domain/          SQLModel tables + Pydantic normalized types (NormalizedLeague, NormalizedRoster, ...)
    providers/
      base.py        FantasyProviderAdapter Protocol (spec §12)
      yahoo/         oauth.py, client.py, parse.py, stat_map.py, adapter.py
      manual/        adapter.py
    nfl_data/
      base.py        NFLDataProvider Protocol (spec §13)
      sleeper_players.py, sleeper_stats.py, espn_schedule.py, composite.py
      stat_keys.py   Sleeper stat field → normalized stat key
    scoring/         engine.py, presets.py
    player_resolution/ resolver.py
    game_day/        service.py, ownership.py, grouping.py
    matchups/        service.py
    cache/           base.py (Cache Protocol), db_cache.py (Postgres TTL table)
    routers/         providers.py, leagues.py, manual_teams.py, players.py, game_day.py, matchups.py
  alembic/
  tests/  unit/, integration/, fixtures/{yahoo,nfl}/
/e2e                 Playwright
docker-compose.yml   postgres (+ api/web for full-stack run)
DECISIONS.md         ADR log (spec §29)
.env.example
```

## Cross-cutting design

- **Anonymous session:** the first request gets an `ff_session` cookie (HTTP-only, Secure, SameSite=Lax, signed opaque ID). The backend creates an anonymous `User` row for it, and every query is scoped by `user_id`. Leagues, teams, and tokens live in Postgres and survive browser restarts. Display filters live in localStorage. This lines up with later account migration in P1.
- **Same origin:** Next.js `rewrites` proxy `/api/*` to FastAPI, so cookies and the Yahoo callback stay on one origin. Secrets stay server-side in FastAPI.
- **Token encryption:** Fernet (`cryptography`) with `TOKEN_ENCRYPTION_KEY`. `ProviderConnection` stores the encrypted access token, encrypted refresh token, `token_expires_at`, and scopes.
- **Normalized boundary:** adapters return only Pydantic `Normalized*` types. Nothing outside `providers/` and `nfl_data/` sees raw payloads.
- **Refresh without a worker:**
  - `game_day` and `matchups` services check cache staleness on read.
  - Stats/schedule TTL is 60s when any game is live, otherwise 1h.
  - Yahoo roster/matchup TTL is 5 min on game day, otherwise 1h. Explicit refresh bypasses the TTL.
  - Sleeper players catalog refreshes at most once a day.
  - Frontend TanStack `refetchInterval` is 60s only while a game is live.
- **Errors:** an `AppError(code, message, http_status)` hierarchy uses the spec §19 codes plus `PROVIDER_AUTH_REQUIRED` and `PROVIDER_AUTH_EXPIRED`. The JSON shape is `{code, message}`. Per-league failures come back inline (`league_errors[]`), so one bad provider never fails the whole page.
- **Observability:** `structlog` JSON logs. Middleware logs request latency. Adapters log provider latency, rate-limit hits, mapping failures, and refresh duration. Tokens are never logged.
- **Rate limiting:** `slowapi` on import, discover, and player-search.

---

## Phases

### Phase 0 — Foundation
- Scaffold both apps:
  - api: `uv init`, plus ruff, mypy, pytest.
  - web: `create-next-app` with TS + Tailwind, then shadcn init.
- Add `docker-compose.yml` with Postgres 16 and `.env.example`.
- Add the Alembic baseline migration with every spec §11 table: User, ProviderConnection, FantasyLeague, FantasyTeam, CanonicalPlayer, RosterSnapshot, RosterEntry, FantasyMatchup, ScoringProfile, NFLGame, PlayerGameStats. Also add:
  - a `player_id_mapping` table (provider, external_id → canonical id, method, confidence) for spec §20
  - a `cache_entry` table
- Define the provider and NFL-data Protocols, the session middleware, error handling, and logging.
- Build the web shell: bottom nav (Games/Matchups/Teams/Settings), TanStack Query provider, and an API client with typed responses.
- Start `DECISIONS.md` with the stack, data sources, no-Redis-in-v1, and the session/token strategy.
- **Deliverable:** `docker compose up db`, `uv run fastapi dev`, and `pnpm dev` all boot, and `/api/health` returns OK.

### Phase 1 — Canonical NFL data
- `sleeper_players.py`: fetch the catalog and upsert `CanonicalPlayer` for skill positions + K + DEF, with sleeper/yahoo/espn/gsis ids. Run it via the CLI `uv run python -m app.nfl_data.sync_players` and a daily lazy refresh.
- `espn_schedule.py`: scoreboard by season/week → `NFLGame`. Map statuses to `scheduled/pregame/live/halftime/final/postponed/canceled`.
- `sleeper_stats.py` + `stat_keys.py`: weekly stats → `PlayerGameStats.raw_stats_json` with normalized keys (`pass_yards`, `pass_td`, `interception`, `rush_yards`, `rush_td`, `reception`, `receiving_yards`, `receiving_td`, `fumble_lost`, `two_pt`, ...). Stats join to games through player team + week schedule.
- Current week comes from Sleeper `/v1/state/nfl`.
- `GET /api/players/search?q=` uses Postgres `pg_trgm` on the normalized name. Also add `GET /api/players/{id}`.
- **Deliverable:** the player search endpoint works, and the week schedule plus stats load into the DB.

### Phase 2 — Scoring engine
- `scoring/engine.py`: pure `calculate_fantasy_points(stats: dict[str, float], rules: NormalizedScoringRules) -> float`. It sums `stats[key] * rules[key]`, rounds to 2 decimals, and covers fractional and negative values.
- Only canonical non-overlapping keys are used, so there's no double-counting (for example, total yards are never derived from both rush and receiving yards).
- `presets.py`: Standard, Half PPR, Full PPR.
- Unit tests for the spec §14 list: passing QB, rushing RB, receiving WR, PPR vs half-PPR, turnovers, mixed RB.
- K/DEF scoring is deferred. Those rows show "points unavailable" instead of hiding the player.

### Phase 3 — Custom teams
- Build `providers/manual/adapter.py` and the `routers/manual_teams.py` CRUD (spec §16 endpoints). A custom team is a `FantasyTeam(provider=manual, is_manual=true, is_user_team=true)` with a `ScoringProfile` from a preset, plus a `RosterSnapshot` for the current week.
- Web: `/teams` lists Connected Leagues, Custom Teams, and Add Team. `/teams/new` is the provider chooser: Yahoo, Custom Team, and a disabled "Sleeper/ESPN coming soon". `/teams/custom/new` is the builder: name → preset → debounced search → add as starter or bench → save.

### Phase 4 — Game-day dashboard
- `ownership.py` classifies rows as `MY_STARTER / MY_BENCH / OPPONENT` per (league, team, player).
- `grouping.py` buckets rows by NFL game. Sort order is live, then upcoming by kickoff, then final.
- `service.py` builds the `GET /api/game-day?season&week` response in the spec §16 shape:
  - Each game includes `my_starters`, `my_bench`, and `opponents`.
  - Each row carries player, position, NFL team, league name, ownership, points, game status, and injury status if available.
  - Bye/no-game players go in a separate group.
  - The response includes `league_errors`.
- Web `/`:
  - week header, refresh button, and filter chips (starters / bench / opponents / all games) persisted in localStorage
  - game cards (away @ home, kickoff or live clock, network, score)
  - player rows with a text ownership badge plus icon, not color alone
  - empty state copy from spec §18.4
  - mobile-first with no horizontal scroll
- **Deliverable:** the full loop works with a custom team.

### Phase 5 — Yahoo import
- **Registration (manual step for you):** create an app at developer.yahoo.com/apps/create with Fantasy Sports **Read** permission and redirect URI `https://localhost:3000/api/providers/yahoo/auth/callback`.
  - Local HTTPS uses `next dev --experimental-https`, which generates a mkcert cert.
  - If Yahoo rejects `localhost`, use a cloudflared/ngrok tunnel URL instead.
  - Put `YAHOO_CLIENT_ID`/`YAHOO_CLIENT_SECRET` in `.env`.
- `oauth.py`:
  - `auth/start` creates a random `state`, stores it in the session, and redirects to `api.login.yahoo.com/oauth2/request_auth` with scope `fspt-r`.
  - `auth/callback` validates `state`, exchanges the code at `/oauth2/get_token`, encrypts and stores the tokens, then redirects to `/teams/yahoo/select`.
  - `ensure_fresh_token()` refreshes about 5 min before expiry. If refresh fails, it raises `PROVIDER_AUTH_EXPIRED`.
  - `DELETE /api/providers/yahoo/connection` deletes the tokens.
- `client.py`: an httpx client on `fantasysports.yahooapis.com/fantasy/v2/` with `format=json`, retry/backoff on 429/999, and latency logging.
- `parse.py`: helpers that flatten Yahoo's awkward JSON (numeric-keyed dicts, lists of single-key dicts). These are tested heavily against recorded fixtures.
- `adapter.py`, implementing the spec §12 interface:
  - `getLeagues`: `users;use_login=1/games;game_keys=nfl/leagues`
  - `getScoringRules`: `league/{key}/settings` stat_categories + stat_modifiers, converted to normalized keys through `stat_map.py`
  - `getTeams`: `league/{key}/teams`. `is_owned_by_current_login` pre-selects the user's team.
  - `getRoster`: `team/{key}/roster;week=N`. `selected_position` BN or IR → bench/IR, everything else → starter.
  - `getMatchups`: `league/{key}/scoreboard;week=N`, including team_points and projected points.
  - Store the numeric part of the player key as `yahoo_id`.
- `resolver.py` (spec §20 priority):
  1. `player_id_mapping`
  2. canonical `yahoo_id`
  3. exact normalized name + team + position
  4. `rapidfuzz` fallback, accepted only at ≥0.92 and logged
  
  Results are saved to the mapping table. Unresolved players log `PLAYER_MAPPING_FAILED` and render as "unmapped" rows.
- Endpoints: `POST /api/providers/yahoo/discover`, `POST /api/leagues/import`, `GET /api/leagues[/{id}[/teams]]`, `POST /api/leagues/{id}/select-team`, `POST /api/leagues/{id}/refresh`.
- Web:
  - `/teams/yahoo/select`: pick leagues, then confirm the pre-selected team for each.
  - Teams screen league cards: provider, name, selected team, last synced, refresh, remove.
  - A "Reconnect Yahoo" banner on `PROVIDER_AUTH_EXPIRED`.

### Phase 6 — Matchups + opponents
- `matchups/service.py` handles `GET /api/matchups?season&week` and `GET /api/matchups/{id}`.
  - **Matchup totals use Yahoo's reported `team_points`.** That is the authoritative league score.
  - Player rows use our engine.
  - A debug log flags any gap of more than 0.5 between Yahoo's total and the engine sum, to catch stat-map bugs.
  - Custom teams appear with "no matchup data".
- Opponent rosters are fetched for the opponents toggle on game-day (spec §10.7). The same player can show up in several contexts, each kept separate.
- Web: `/matchups` shows one card per league (league, my team vs opponent, scores, projected, status). Tapping a card opens a detail view with both starting lineups.

### Phase 7 — Hardening
- Stale/unavailable indicators ("Stats as of 1:42 PM", "Live data unavailable"), loading skeletons, and actionable error copy.
- Mobile polish pass, plus a `/settings` page: default filters, disconnect Yahoo, clear local data.
- Deployment target noted in `DECISIONS.md` (Vercel web + Render/Fly API + managed Postgres, same-origin via rewrites). The actual deploy waits for your go-ahead.

---

## Testing & verification

- **Unit (pytest):**
  - scoring engine (spec §14 cases)
  - resolver priority and fuzzy threshold
  - Yahoo `parse.py`/`stat_map.py` against fixtures
  - ESPN status mapping
  - `ownership.py` and `grouping.py`, including one player in 3 leagues and sort order
- **Integration (pytest + respx + Postgres from compose):**
  - mocked Yahoo OAuth connect and token refresh
  - import fixture league → normalize → select team → load matchup
  - combine with fixture ESPN schedule + Sleeper stats
  - assert the grouped `/api/game-day` JSON
  - expired refresh token → `PROVIDER_AUTH_EXPIRED`
  - one provider failing → the page still renders, with `league_errors`
- **E2E (Playwright):** the backend runs with `FIXTURE_MODE=1`, which swaps in fixture-backed providers and a fake Yahoo OAuth. The test covers the spec §23 UI flows 1–9, run at mobile and desktop viewports.
- **Manual end-to-end on a real Sunday:** `docker compose up db`, then API + `pnpm dev --experimental-https`, then:
  1. Connect a real Yahoo league and create a custom team.
  2. On `/`, check games and points against Yahoo's app.
  3. Toggle bench and opponents.
  4. Check that `/matchups` totals match Yahoo.
  5. Restart the browser and confirm the configuration persists.
- **Fixture capture:** a script records real Yahoo/ESPN/Sleeper responses (scrubbed of tokens and names) into `tests/fixtures/`, so tests never hit live services.

## Open risks
- Yahoo redirect URIs may not accept `localhost`. The tunnel fallback covers this.
- The Sleeper stats and ESPN scoreboard endpoints are unofficial. They sit behind `NFLDataProvider`, so they can be swapped for a licensed API later, and the ADR records this.
- Engine vs Yahoo point differences from unusual stat categories. Matchup totals use Yahoo's number, and differences are logged.
