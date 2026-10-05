# Fantasy Football Game-Day Companion — MVP Product & Engineering Specification

## 1. Purpose of This Document

This document is the source of truth for the first implementation of a fantasy football web application inspired by the core product concept of Fantasy Playtime.

The goal is **not** to clone branding, copy proprietary code, or reproduce every edge feature. The goal is to build the same core category of product: a **cross-platform fantasy football game-day companion** that lets a user connect multiple fantasy teams and understand, in one place, which NFL games and players matter to them each week.

The coding agent should use this document to:

1. Understand the user problem and intended product behavior.
2. Design the initial application architecture.
3. Build the MVP in clearly separated phases.
4. Avoid spending time on features explicitly marked out of scope.
5. Make implementation decisions that support future Sleeper/ESPN/Fleaflicker integrations without coupling the MVP to any one fantasy provider.

---

## 2. Product Vision

A fantasy football user may participate in several leagues across different providers. On NFL game day, it is cumbersome to jump between ESPN, Sleeper, Yahoo, Fleaflicker, and other apps simply to answer questions such as:

- Which NFL games contain players from my fantasy teams?
- Which of my starters are currently playing?
- Which bench players are playing?
- Which players belong to my fantasy opponent this week?
- How many fantasy points has each player scored in the scoring system of each league?
- How am I doing across all of my fantasy matchups?

The application should solve this with a **single cross-league dashboard**.

The core product principle is:

> Organize fantasy football around the live NFL games the user is watching, not around the fantasy platform the user happened to join.

This is primarily a **game-day companion**, not an advice product.

---

## 3. Core User Story

A typical user has four fantasy teams:

- ESPN league A
- ESPN league B
- Sleeper league C
- Yahoo league D

Instead of opening four separate applications on Sunday, the user opens this application and immediately sees:

- all relevant NFL games,
- their starters grouped under each NFL game,
- optional bench players,
- optional players belonging to their current fantasy opponents,
- current fantasy points calculated using the correct scoring rules for each league,
- and all fantasy matchups across their connected leagues.

Example:

```text
BUF vs NE — 1:00 PM — CBS

MY PLAYERS
Josh Allen       League A       18.42 pts
James Cook       League C       10.70 pts

OPPONENT PLAYERS
Stefon Diggs     League B       12.30 pts
```

The application should make it obvious why each NFL game matters to the user.

---

## 4. MVP Definition

The MVP should prove the following loop end-to-end:

```text
Connect fantasy league(s)
        ↓
Normalize league + roster data
        ↓
Map fantasy players to canonical NFL players
        ↓
Map canonical players to the current NFL schedule
        ↓
Display fantasy-relevant NFL games
        ↓
Display current fantasy points for those players
        ↓
Display all current fantasy matchups in one place
```

A successful MVP allows a real user to connect at least one supported fantasy provider, select their fantasy team, and use the app during an NFL Sunday without needing to reopen the original fantasy platform for basic game-day tracking.

---

## 5. MVP Scope

### 5.1 P0 — Must Be Built

The following features are required for MVP.

#### Authentication / User State

- Application must work in anonymous/local mode first.
- The user should not be forced to create an account before trying the product.
- Persist anonymous configuration locally in the browser.
- Architecture must allow cloud accounts and cross-device sync later.
- Yahoo requires OAuth, so anonymous mode needs a server-side anonymous session (e.g., an opaque session ID in an HTTP-only cookie) that owns the user's encrypted Yahoo tokens. Tokens must never be stored in browser localStorage.

#### Fantasy Provider Integration

Support in the first version:

1. **Yahoo — P0.** Integrate through the official Yahoo Fantasy Sports API using OAuth 2.0 with read-only scope. Yahoo is the first fully working provider.
2. **Custom team creation — P0.** A first-class way to build a roster by hand (see Custom Fantasy Team below), for users whose provider isn't supported yet or who just want to track a team quickly.

Deferred to P1, but the architecture must anticipate them:

- Sleeper
- ESPN
- Fleaflicker

Do not tightly couple business logic to Yahoo data structures.

#### Team Selection

After importing a league:

- show all fantasy teams in the league,
- allow the user to identify/select their own fantasy team,
- persist that selection,
- store the current roster split into starters and bench.

#### Multiple Leagues

The user must be able to connect multiple leagues.

The application must support one NFL player appearing in multiple fantasy leagues simultaneously.

Example:

```text
Josh Allen
- My starter in League A
- My opponent's starter in League B
- My starter in League C
```

Each context must remain separately visible because scoring rules may differ.

#### Canonical Player Model

Create an internal player identity layer.

A fantasy provider's player ID must never become the application's canonical player ID.

Each internal player record should support mappings such as:

```text
internal_player_id
full_name
first_name
last_name
position
nfl_team
status
espn_id
sleeper_id
yahoo_id
fleaflicker_id
gsis_id
external_stats_provider_id
```

Not every field must be populated immediately, but the schema should support this model.

#### NFL Weekly Schedule

For the current fantasy week, retrieve:

- NFL games,
- home team,
- away team,
- kickoff time,
- game status,
- current score if available,
- quarter/time remaining if available,
- broadcaster/network if the data provider exposes it.

The application must understand states such as:

```text
scheduled
pregame
live
halftime
final
postponed/canceled if supplied by provider
```

#### Game-Centric Dashboard

This is the primary screen and the central MVP feature.

Group fantasy-relevant players by real NFL game.

By default show:

- user's starters,
- current fantasy points,
- fantasy league/team context,
- whether the player's NFL game is scheduled, live, or final.

Provide controls for:

- Show/hide bench players.
- Show/hide opponent players.
- Show all NFL games, including games with no fantasy relevance.

A player displayed under a game must include enough context to distinguish duplicate ownership across leagues.

Minimum player row:

```text
Player name
Position
NFL team
Fantasy league name
Ownership context: MY STARTER / MY BENCH / OPPONENT
Current fantasy points
```

Useful optional row fields:

- projected fantasy points,
- injury status,
- current stat line.

#### Fantasy Matchups Screen

Create a consolidated screen showing all of the user's current weekly fantasy matchups.

Minimum matchup card:

```text
League name
My fantasy team name
My current fantasy score
Opponent team name
Opponent current fantasy score
Week
Status / projected outcome if available
```

The matchup detail view should show starters for both sides when data is available.

#### League-Specific Scoring

Do not assume one universal scoring model.

Implement scoring as:

```text
raw player statistics
        ↓
league scoring rules
        ↓
fantasy points for that player in that league
```

At minimum support presets:

- Standard
- Half PPR
- Full PPR

If the provider exposes complete custom league scoring rules, save them in a normalized scoring rules structure.

Scoring logic must be isolated in its own service/module.

#### Custom Fantasy Team

Users must be able to create a custom team by hand, whether or not their provider has automatic import. Internally these are "manual" teams (`provider = manual`, `is_manual = true`).

Minimum workflow:

1. Create custom team.
2. Enter team name.
3. Select scoring preset.
4. Search canonical NFL player database.
5. Add players as starters or bench.
6. Save locally.
7. Custom team appears everywhere an imported team would appear.

Custom teams must use the same normalized internal domain objects as provider-imported teams.

#### Responsive UI

The product is likely to be used heavily on game day from a phone.

Requirements:

- Responsive mobile-first layout.
- Desktop should also work well as a second-screen dashboard.
- Do not require horizontal scrolling for core usage.

---

## 6. P1 — Build After Core MVP Works

These should be anticipated but should not block MVP completion.

### Additional Providers

- Sleeper import (see 10.4)
- ESPN import (see 10.5)
- Fleaflicker import

Each should be implemented as a provider adapter returning the same normalized domain model.

### Account Authentication

Add user accounts after anonymous experience is reliable.

Desired flow:

```text
Anonymous configuration
        ↓
User creates/signs into account
        ↓
Local leagues + preferences migrate to cloud profile
        ↓
Configuration is available on another device
```

### Cross-Device Sync

Persist:

- connected leagues,
- selected fantasy teams,
- manual teams,
- display preferences,
- notification settings.

### Injuries

Display current injury status for fantasy-relevant players.

Possible statuses:

```text
healthy
questionable
doubtful
out
IR
PUP
suspended
```

### Projections

Show projected fantasy points when a reliable source is available.

Projection data must remain distinct from actual fantasy scoring.

### Standings

League-level standings view:

- rank,
- team,
- wins,
- losses,
- ties if applicable,
- points for,
- points against if available.

### Screenshot Roster Import

Allow a user to upload a fantasy roster screenshot and extract players using a multimodal model.

Preferred pipeline:

```text
Screenshot
   ↓
multimodal structured extraction
   ↓
player-name candidates
   ↓
canonical NFL-player entity resolution
   ↓
confidence scores
   ↓
user confirmation UI
   ↓
manual roster creation
```

Do not rely solely on OCR if a multimodal model is available.

Expected structured output example:

```json
{
  "team_name": "Ankit's Team",
  "starters": [
    {"name": "Josh Allen", "position": "QB"},
    {"name": "Bijan Robinson", "position": "RB"}
  ],
  "bench": [
    {"name": "Player Name", "position": "WR"}
  ]
}
```

Entity resolution must handle abbreviated names and ambiguous matches.

---

## 7. P2 — Later Features

Do not build these before P0/P1 are stable.

- Historical weekly lineups
- Historical matchup results
- Injury push/email alerts
- Advanced custom scoring editor
- Light/dark theme if not trivial
- League history views
- Season analytics
- Real-time win probability
- Voice assistant
- AI game-day summaries

---

## 8. Explicit Non-Goals for MVP

Do **not** build the following initially:

- AI start/sit recommendations
- Trade analyzer
- Waiver-wire recommendations
- Draft assistant
- DFS tools
- Sports betting integration
- Social network/feed
- News aggregation feed
- Expert rankings
- Paid subscription/paywall
- Commissioner tools
- League chat
- Full league-management capabilities

The product should remain a game-day aggregation and tracking experience first.

---

## 9. Product Navigation

Keep the navigation intentionally small.

Recommended primary routes:

```text
/                 → Schedule / Game-Day dashboard
/matchups         → Cross-league fantasy matchups
/teams            → Connected leagues + manual teams
/settings         → Display/preferences/provider management
```

Optional later routes:

```text
/leagues/:id
/players/:id
/history
/account
```

Mobile bottom navigation can use:

```text
Games
Matchups
Teams
Settings
```

---

## 10. Detailed User Flows

### 10.1 First Visit

```text
Landing / empty dashboard
        ↓
"Add Fantasy Team"
        ↓
Choose provider
        ↓
Yahoo / Custom Team
```

Do not force account creation. (Connecting Yahoo requires signing in with Yahoo, but not creating an account in this app.)

Sleeper and ESPN can be shown as "Coming soon" options that point users to Custom Team in the meantime.

### 10.2 Yahoo Import (P0)

Likely flow:

```text
Choose Yahoo
        ↓
"Sign in with Yahoo" (OAuth 2.0 authorization code flow, read-only Fantasy Sports scope)
        ↓
Backend exchanges code for tokens, encrypts them, and attaches them to the anonymous session
        ↓
Fetch the user's NFL leagues for the current season
        ↓
Choose league(s)
        ↓
Display teams in league (pre-select the team Yahoo marks as owned by the signed-in user)
        ↓
User confirms their team
        ↓
Normalize league + roster + matchup + scoring settings
        ↓
Save
```

Requirements:

- Run the OAuth exchange and token refresh on the server only. The Yahoo client secret must never reach the browser.
- Yahoo access tokens are short-lived. Refresh them on the server, and if the refresh token is revoked or invalid, show a clear "Reconnect Yahoo" state.
- Request JSON responses (`format=json`); Yahoo returns XML by default.
- Yahoo player keys are season-scoped (`{game_key}.p.{player_id}`). Store the stable numeric `player_id` as `yahoo_id` on the canonical player, not the full key.
- Yahoo league scoring settings use numeric `stat_id`s. Keep a `stat_id` → normalized stat-name mapping in the Yahoo adapter so scoring rules convert into the normalized `ScoringProfile`.
- Provide a "Disconnect Yahoo" action that deletes stored tokens.
- Respect Yahoo API rate limits; cache league/roster responses per the refresh strategy in Section 17.

### 10.3 Custom Team Creation (P0)

```text
Create Custom Team
        ↓
Team name
        ↓
Scoring preset
        ↓
Search players
        ↓
Add starter/bench
        ↓
Save
        ↓
Team appears on Games and Matchups-compatible surfaces
```

Custom teams may not have opponent matchup data unless the user manually supplies it. That is acceptable.

### 10.4 Sleeper Import (P1)

Likely flow:

```text
Choose Sleeper
        ↓
Enter username OR league ID depending on API path
        ↓
Fetch leagues
        ↓
Choose league(s)
        ↓
Display teams in league
        ↓
User identifies their team
        ↓
Normalize league + roster + matchup data
        ↓
Save
```

### 10.5 ESPN Import (P1)

The coding agent should research the safest supported/read-only integration pattern available at implementation time.

Requirements:

- Prefer league ID / public read-only access when possible.
- Avoid requesting or storing the user's ESPN password.
- If private-league authentication requires fragile unofficial cookies or unsupported behavior, isolate it behind the provider adapter and do not allow it to contaminate the core architecture.

If private-league ESPN access proves impractical, return a clear unsupported/private-league error that points the user to custom team creation.

### 10.6 Game-Day Dashboard

On page load:

1. Determine current NFL/fantasy week.
2. Fetch/cache current NFL schedule.
3. Load all user's roster contexts.
4. Resolve each canonical player to NFL team/game.
5. Load latest player stats.
6. Calculate league-specific fantasy scores.
7. Group players by NFL game.
8. Render relevant games chronologically.

Default sorting:

1. live games,
2. upcoming games by kickoff,
3. final games.

Alternative acceptable sorting is chronological if implementation is simpler initially.

### 10.7 Opponent Toggle

When opponent players are enabled:

- retrieve current opponent for each connected fantasy league,
- retrieve opponent starting lineup,
- map those players into NFL games,
- label them visually as `OPPONENT`,
- never merge them semantically with the user's own players.

If the same NFL player appears in different ownership contexts across different leagues, show all relevant contexts.

---

## 11. Domain Model

The following model is recommended conceptually. Exact ORM syntax can vary.

### User

```text
User
- id
- email nullable for anonymous/local mode
- created_at
- updated_at
```

### ProviderConnection

```text
ProviderConnection
- id
- user_id
- provider
- external_account_identifier nullable
- encrypted_access_token nullable (required for Yahoo)
- encrypted_refresh_token nullable (required for Yahoo)
- token_expires_at nullable
- scopes nullable
- created_at
- updated_at
```

Never store plaintext provider passwords.

### FantasyLeague

```text
FantasyLeague
- id
- user_id / ownership relation as appropriate
- provider
- external_league_id
- name
- season
- current_week
- scoring_profile_id
- created_at
- updated_at
```

### FantasyTeam

```text
FantasyTeam
- id
- league_id nullable for manual team
- provider
- external_team_id nullable
- name
- owner_name nullable
- is_user_team
- is_manual
```

### CanonicalPlayer

```text
CanonicalPlayer
- id
- first_name
- last_name
- full_name
- position
- nfl_team_code nullable
- active_status
- gsis_id nullable
- sleeper_id nullable
- espn_id nullable
- yahoo_id nullable
- fleaflicker_id nullable
- stats_provider_id nullable
```

### RosterSnapshot

Use snapshots rather than only storing a mutable current roster.

```text
RosterSnapshot
- id
- fantasy_team_id
- season
- week
- fetched_at
```

### RosterEntry

```text
RosterEntry
- id
- roster_snapshot_id
- player_id
- slot
- is_starter
- is_bench
- is_ir
```

### FantasyMatchup

```text
FantasyMatchup
- id
- league_id
- season
- week
- user_team_id
- opponent_team_id
- user_score
- opponent_score
- status
- fetched_at
```

### ScoringProfile

```text
ScoringProfile
- id
- league_id nullable
- name
- scoring_json
```

`scoring_json` should contain normalized statistic-to-point mappings.

Example:

```json
{
  "pass_yards": 0.04,
  "pass_td": 4,
  "interception": -2,
  "rush_yards": 0.1,
  "rush_td": 6,
  "reception": 1,
  "receiving_yards": 0.1,
  "receiving_td": 6,
  "fumble_lost": -2
}
```

### NFLGame

```text
NFLGame
- id
- external_game_id
- season
- week
- kickoff_at
- home_team
- away_team
- home_score
- away_score
- status
- quarter
- clock
- broadcaster nullable
- updated_at
```

### PlayerGameStats

```text
PlayerGameStats
- id
- game_id
- player_id
- raw_stats_json
- updated_at
```

Do not store a single universal fantasy score here because scoring is league-dependent.

---

## 12. Provider Adapter Architecture

Create a provider interface similar to:

```typescript
interface FantasyProviderAdapter {
  getLeagues(input: ProviderAccountInput): Promise<NormalizedLeague[]>;
  getLeague(leagueId: string): Promise<NormalizedLeague>;
  getTeams(leagueId: string): Promise<NormalizedFantasyTeam[]>;
  getRoster(teamId: string, week: number): Promise<NormalizedRoster>;
  getMatchups(leagueId: string, week: number): Promise<NormalizedMatchup[]>;
  getScoringRules(leagueId: string): Promise<NormalizedScoringRules>;
  getStandings?(leagueId: string): Promise<NormalizedStanding[]>;
}
```

Implement provider-specific modules:

```text
providers/
  sleeper/
  espn/
  yahoo/
  fleaflicker/
  manual/
```

Nothing outside the provider layer should need to know the provider's original API response schema.

---

## 13. NFL / Sports Data Abstraction

Create a separate interface for real NFL data.

```typescript
interface NFLDataProvider {
  getSchedule(season: number, week: number): Promise<NFLGame[]>;
  getGame(gameId: string): Promise<NFLGame>;
  getPlayerGameStats(gameId: string): Promise<PlayerGameStats[]>;
  getPlayers(): Promise<CanonicalNFLPlayer[]>;
  getInjuries?(): Promise<PlayerInjury[]>;
  getProjections?(week: number): Promise<PlayerProjection[]>;
}
```

This layer must be independent from fantasy providers.

The coding agent should evaluate current NFL/fantasy-data providers before implementation and document:

- licensing restrictions,
- API limits,
- live-data latency,
- player-ID quality,
- schedule coverage,
- stats coverage,
- pricing/free tier.

Do not scrape consumer sites as the long-term data source if an API can be used instead.

---

## 14. Fantasy Scoring Engine

Create a pure scoring function/module.

Input:

```text
raw player statistics
+ normalized scoring rules
```

Output:

```text
fantasy points
```

Example interface:

```typescript
calculateFantasyPoints(
  stats: PlayerStatLine,
  scoring: NormalizedScoringRules
): number
```

Requirements:

- deterministic,
- independently unit testable,
- provider agnostic,
- support fractional scoring,
- handle negative scoring,
- avoid double-counting overlapping stats.

Create unit tests for at least:

- passing QB,
- rushing RB,
- receiving WR,
- PPR versus half-PPR difference,
- turnovers,
- mixed rushing/receiving player.

Defense/special teams and kicker scoring can be deferred if the initial sports-data source makes them disproportionately complex, but the schema should not prevent adding them.

---

## 15. Suggested Technical Stack

Unless there is a strong reason to deviate, use:

### Frontend

- Next.js
- TypeScript
- React
- Tailwind CSS
- Component library such as shadcn/ui if useful
- TanStack Query or equivalent for server-state caching

### Backend

Either:

**Option A — FastAPI backend**

- FastAPI
- Pydantic
- SQLAlchemy / SQLModel

or, if the coding agent determines one full-stack TypeScript application materially reduces MVP complexity:

**Option B — Next.js server/API layer**

The key requirement is clean separation of domain/services/provider adapters, not language purity.

Preferred architecture based on current intent:

```text
Next.js frontend
        ↓
FastAPI backend
        ↓
PostgreSQL
        ↓
Redis cache
```

### Data

- PostgreSQL for persistent normalized entities
- Redis for live/cached data if needed

Redis can initially be optional if deployment complexity is unnecessary. Design caching behind an interface so it can be introduced when live polling volume increases.

### Deployment

Prefer simple developer-friendly deployment:

- Vercel for Next.js frontend
- Render/Fly.io/Railway/AWS for backend
- managed Postgres

The coding agent may choose a different host if it materially simplifies the implementation.

---

## 16. API Endpoints — Initial Proposal

Exact naming can change, but the first backend should expose functionality equivalent to the following.

### Teams / Providers

```text
GET    /api/providers
GET    /api/providers/yahoo/auth/start
GET    /api/providers/yahoo/auth/callback
POST   /api/providers/yahoo/discover
DELETE /api/providers/yahoo/connection
POST   /api/leagues/import
GET  /api/leagues
GET  /api/leagues/{league_id}
GET  /api/leagues/{league_id}/teams
POST /api/leagues/{league_id}/select-team
```

P1 providers will add equivalent endpoints (e.g., `POST /api/providers/sleeper/discover`, `POST /api/providers/espn/discover`).

### Manual (Custom) Teams

```text
POST   /api/manual-teams
GET    /api/manual-teams
PATCH  /api/manual-teams/{id}
DELETE /api/manual-teams/{id}
POST   /api/manual-teams/{id}/players
DELETE /api/manual-teams/{id}/players/{player_id}
```

### Players

```text
GET /api/players/search?q=
GET /api/players/{id}
```

### Game Day

```text
GET /api/game-day?season=2026&week=5
```

Ideal response should already be grouped for UI rendering.

Conceptual response:

```json
{
  "week": 5,
  "games": [
    {
      "game": {},
      "my_starters": [],
      "my_bench": [],
      "opponents": []
    }
  ]
}
```

Do not require the frontend to independently join six unrelated endpoints to render the primary page.

### Matchups

```text
GET /api/matchups?season=2026&week=5
GET /api/matchups/{id}
```

---

## 17. Data Refresh Strategy

The application should not continuously hammer fantasy or NFL APIs.

Recommended model:

### Fantasy League Data

Refresh:

- on explicit user refresh,
- when opening the app after a reasonable stale interval,
- periodically around game day if needed.

Roster/team metadata does not require second-by-second refresh.

### Live NFL Data

During active NFL games:

- poll at a reasonable interval based on provider limits, OR
- consume push/WebSocket data if supplied.

The backend should update cached raw statistics, recalculate fantasy values, and expose fresh game-day data.

Future architecture:

```text
NFL stats update
      ↓
cache/store raw stat update
      ↓
identify affected player
      ↓
calculate scores per relevant league scoring profile
      ↓
push UI update via SSE/WebSocket
```

For the first MVP, polling is acceptable if reliable and within provider limits.

---

## 18. Frontend Screen Requirements

### 18.1 Games / Schedule Screen

Header should show:

- current week,
- date/week navigation if implemented,
- refresh action,
- filters.

Filters:

```text
[x] My starters
[ ] Bench
[ ] Opponents
[ ] All NFL games
```

Each NFL game card:

```text
Away Team @ Home Team
Kickoff OR live status
Broadcast network if known
NFL score if live/final
```

Then grouped fantasy players.

Ownership labels must be visually distinct.

Do not use color alone to convey ownership state; include a textual label/icon for accessibility.

### 18.2 Matchups Screen

Render one card per league.

Each card:

```text
League name
My team vs Opponent
Current score
Game/week status
```

Click/tap expands or navigates to lineup detail.

### 18.3 Teams Screen

Sections:

```text
Connected Leagues
Manual Teams
Add Team
```

Each imported league should show:

- provider,
- league name,
- selected fantasy team,
- last synced time,
- sync/refresh action,
- remove action.

### 18.4 Empty State

The first-time user must understand the value immediately.

Suggested copy direction:

> Connect your fantasy teams and see every NFL game that matters to you in one place.

Primary action:

```text
Add Fantasy Team
```

---

## 19. Error Handling

Provider integrations will fail in many ways. Handle errors explicitly.

Examples:

```text
LEAGUE_NOT_FOUND
PRIVATE_LEAGUE_UNSUPPORTED
INVALID_LEAGUE_ID
PROVIDER_RATE_LIMITED
PROVIDER_UNAVAILABLE
PROVIDER_AUTH_REQUIRED
PROVIDER_AUTH_EXPIRED
TEAM_NOT_SELECTED
PLAYER_MAPPING_FAILED
LIVE_DATA_UNAVAILABLE
```

User-facing errors should be actionable.

Bad:

> Something went wrong.

Good:

> Your Yahoo connection has expired. Reconnect Yahoo to refresh League D, or create the roster as a custom team instead.

---

## 20. Player Entity Resolution

This is critical.

Provider IDs must map to one canonical player entity.

Resolution priority:

1. known provider-ID mapping,
2. GSIS or stable NFL identifier,
3. exact normalized name + team + position,
4. fuzzy name matching only as fallback.

Never silently accept a low-confidence fuzzy player match for screenshot/manual import.

Potential normalized key:

```text
normalized_name
position
nfl_team
birthdate if provider supplies it
```

Maintain a mapping table so future refreshes do not repeatedly perform fuzzy matching.

---

## 21. Privacy and Security

Requirements:

- Never ask for or store fantasy-provider plaintext passwords.
- Encrypt Yahoo OAuth access and refresh tokens at rest (P0). Apply the same rule to any future provider tokens.
- Validate the OAuth `state` parameter on the Yahoo callback to prevent CSRF.
- Request only read-only Yahoo Fantasy Sports scope.
- Validate uploaded screenshots before processing.
- Delete temporary screenshot files after extraction unless the user explicitly saves them.
- Do not expose one user's fantasy data to another user.
- Treat external provider IDs as identifiers, not authorization.
- Rate-limit import and player-search endpoints.
- Do not expose backend provider secrets to the browser.

---

## 22. Observability

At minimum log:

- provider-import attempts and result status,
- provider latency,
- API rate-limit errors,
- player mapping failures,
- data refresh duration,
- scoring-engine errors,
- game-day endpoint latency.

Do not log provider credentials/tokens or unnecessary user-sensitive payloads.

Useful metrics later:

```text
connected leagues per user
providers used
weekly active game-day users
percentage of mappings resolved automatically
average game-day refresh latency
provider error rate
```

---

## 23. Testing Requirements

### Unit Tests

Required modules:

- fantasy scoring engine,
- player ID/entity resolver,
- provider normalization,
- game grouping logic,
- ownership classification logic.

### Integration Tests

At minimum:

- complete a mocked Yahoo OAuth connect and token refresh,
- import mock Yahoo league,
- normalize teams, rosters, and Yahoo `stat_id` scoring settings,
- identify user team,
- load matchup,
- combine with mock NFL schedule,
- calculate scores,
- return grouped game-day response.

### UI Tests

Cover critical flows:

1. first-time add team,
2. connect Yahoo and import league,
3. choose team,
4. dashboard renders relevant NFL games,
5. bench toggle,
6. opponent toggle,
7. matchup list,
8. custom team creation,
9. Yahoo reconnect after expired/revoked tokens.

Provider API responses should be fixture-driven in tests so tests do not depend on live third-party services.

---

## 24. MVP Acceptance Criteria

The MVP is considered complete when all of the following are true.

### Import

- A user can connect a Yahoo account and import at least one real Yahoo league.
- User can select their team.
- Multiple connected leagues can coexist, including Yahoo leagues alongside custom teams.
- A custom team can be created and appears on the Games and Teams screens.

### Data Normalization

- Provider-specific roster data becomes normalized domain entities.
- Canonical player mappings work for the overwhelming majority of active rostered players in a normal league.

### Game Day

- Current NFL schedule loads.
- User's starters are mapped to relevant NFL games.
- Bench toggle works.
- Opponent toggle works for imported leagues with matchup data.
- Player fantasy score is calculated using the correct league scoring profile.
- The same player can appear correctly in multiple league contexts.

### Matchups

- All available current-week user matchups render on one screen.
- User and opponent current scores display.

### Persistence

- Anonymous user's configuration survives page refresh/browser restart on the same device.

### Reliability

- A single unavailable provider does not crash the whole application.
- Errors are surfaced clearly.
- API secrets remain server-side.

### UX

- Core experience works on modern mobile and desktop browsers.
- A new user can reach a useful dashboard without creating an account.

---

## 25. Recommended Build Phases

### Phase 0 — Project Foundation

Build:

- repo structure,
- frontend shell,
- backend shell,
- database schema/migrations,
- environment configuration,
- domain models,
- provider interfaces,
- NFL data interface.

Deliverable: application boots locally and core abstractions exist.

### Phase 1 — Yahoo Import

Build:

- Yahoo developer app registration + OAuth 2.0 flow,
- anonymous server-side session + encrypted token storage/refresh,
- Yahoo adapter,
- league discovery/import,
- team selection,
- roster normalization,
- matchup normalization,
- scoring rule normalization (`stat_id` mapping).

Deliverable: real Yahoo league can be imported and inspected in normalized JSON/UI.

### Phase 2 — Canonical NFL Data

Build:

- player catalog,
- player mapping,
- current schedule,
- live/raw player stats ingestion,
- caching.

Deliverable: imported fantasy roster players resolve to NFL players and games.

### Phase 3 — Game-Day Dashboard

Build:

- relevant-game grouping,
- player context rows,
- starter/bench/opponent classification,
- live score calculation,
- filters.

Deliverable: primary product experience works.

### Phase 4 — Matchups

Build:

- consolidated matchup endpoint,
- matchup cards,
- matchup detail.

Deliverable: user can see all current fantasy contests on one page.

### Phase 5 — Custom Teams

Build:

- player search,
- team builder,
- scoring preset,
- persistence,
- game-day integration.

Deliverable: users on Sleeper, ESPN, or any other not-yet-supported provider can still use the product.

### Phase 6 — Hardening

Build:

- provider error handling,
- stale-data handling,
- loading/empty states,
- mobile polish,
- test suite,
- observability,
- deployment.

Deliverable: usable MVP.

### Phase 7 — Sleeper / ESPN / Additional Providers (P1)

Build after the core domain model proves stable. Sleeper first (public read-only API, lowest effort), then ESPN, then Fleaflicker.

---

## 26. Suggested Repository Structure

One possible structure:

```text
/apps
  /web
  /api

/packages or backend modules
  /domain
  /providers
    /sleeper
    /espn
    /yahoo
    /fleaflicker
    /manual
  /nfl-data
  /scoring
  /player-resolution
  /game-day
  /matchups

/tests
  /fixtures
    /yahoo
    /nfl
```

If frontend and backend are separate repositories, preserve the same logical boundaries.

---

## 27. Coding Principles for the Agent

1. **Normalize at system boundaries.** Never let provider-specific payloads leak into UI business logic.
2. **Keep scoring deterministic and testable.**
3. **Prefer canonical IDs over names.**
4. **Make external integrations replaceable.** APIs and pricing can change.
5. **Do not overengineer real-time behavior before the basic Sunday flow works.** Polling is acceptable for MVP.
6. **Build anonymous/local-first onboarding.** Reduce signup friction.
7. **Design mobile-first.**
8. **Use fixtures for external API testing.**
9. **Do not silently hide incomplete data.** Indicate stale/unavailable states.
10. **Do not expand scope into fantasy advice features during MVP.**

---

## 28. Assumptions Made for This Specification

These are implementation assumptions, not immutable product requirements.

1. The MVP begins as a responsive web application rather than native iOS/Android.
2. Yahoo is the first fully supported provider. It has an official, documented API with OAuth 2.0, so private leagues can be imported without fragile cookie-based workarounds.
3. Custom team creation ships in P0, so users on any provider can get value on day one.
4. Sleeper, ESPN, and Fleaflicker are P1 provider integrations.
5. Account creation is not required before a user can test the product. Yahoo sign-in is needed only to import Yahoo leagues.
6. Live NFL data may initially use polling rather than WebSockets/SSE.
7. The exact sports-data provider has intentionally not been hardcoded; select one based on current API quality, licensing, latency, pricing, and player-ID coverage.
8. Initial product positioning is a game-day companion, not an AI fantasy advisor.

If any of these assumptions change, update this document before implementing dependent features.

---

## 29. Decisions That Should Be Recorded Before Production

The coding agent should maintain a short Architecture Decision Record (ADR) or `DECISIONS.md` for the following once selected:

- final frontend/backend stack,
- chosen NFL statistics/data provider,
- chosen production database,
- Yahoo OAuth token storage, encryption, and anonymous-session strategy,
- provider authentication strategy for ESPN (P1),
- canonical player-ID source,
- polling interval/live update mechanism,
- account/authentication provider,
- deployment topology,
- whether Redis is necessary in v1.

---

## 30. Future Product Differentiation

Once the base aggregation product works, a useful intelligence layer can be added without changing the core product philosophy.

Potential future feature:

### "What Matters Right Now?"

Example:

```text
You're currently winning 3 of 4 fantasy matchups.

Highest-impact games:

BUF vs NE
Josh Allen needs roughly 7 more fantasy points for you to take the lead in League A.

DAL vs HOU
Your opponent has two active starters. You currently lead by 12.8.

PHI vs LA
No remaining players in this game affect your fantasy matchups.
```

This can eventually combine live scores, remaining players, projections, and matchup state.

This feature is **not MVP scope**.

### Owner Wishlist

Features the product owner specifically wants to add after the MVP. None of these are MVP scope, and each needs its own design pass before work starts.

#### AI Integration

Bring AI into the app in some form. The specific use cases are still to be brainstormed. Candidates already mentioned elsewhere in this spec include AI game-day summaries (P2), screenshot roster import (P1), and the "What Matters Right Now?" view above.

#### Betting Mode

An opt-in setting, off by default. When it's on, pull player prop lines from a major sportsbook for every player in the user's fantasy matchups and show bets that line up with the user's fantasy interests.

Default behavior ("double down"):

- **User's players:** show props that pay out if the player does well (e.g. overs on yards, anytime TD). The user profits when their fantasy player succeeds.
- **Opponent's players:** show props that pay out if the player does poorly (e.g. unders). The user has another reason to root against the opponent.

**Hedge toggle:** flips both directions so a bet offsets the fantasy outcome rather than amplifying it.

| Player | Hedge off (double down) | Hedge on |
|---|---|---|
| User's player | Bet the player does well (over) | Bet the player does poorly (under) |
| Opponent's player | Bet the player does poorly (under) | Bet the player does well (over) |

Open questions:

- Odds data source (sportsbook API, aggregator such as The Odds API, or affiliate feed) and its licensing terms.
- Legal and geographic restrictions: only show betting content where sports betting is legal and the user is of age, which likely requires location checks.
- Responsible-gambling requirements, such as disclaimers and help resources.
- Whether to deep-link into the sportsbook's bet slip or only display lines.

#### Local Sports Bar Finder

With the user's permission, use their location to suggest nearby sports bars to watch the games. Show each bar's team affiliation where one exists, e.g. a known New York Giants bar.

Open questions:

- Bar data source (Google Places, Yelp, or similar) and where team-affiliation data comes from, e.g. curated lists, user submissions, or fan-club directories.
- Whether to rank bars by the user's fantasy-relevant teams or their favorite NFL team.
- Location privacy: request location only when the user opens this feature, and don't store precise location longer than needed (see Section 21).

---

## 31. Final Product Summary

Build a cross-platform fantasy football game-day companion with the following central promise:

> Connect your fantasy teams once and see every NFL game, fantasy player, and matchup that matters to you in one place.

The MVP is successful if it provides a clean loop from fantasy league import → normalized rosters → NFL games → league-specific fantasy scoring → unified game-day and matchup views.

Focus engineering effort on:

- provider normalization,
- canonical player identity,
- league scoring rules,
- live NFL data,
- and a simple, highly usable game-centric UI.

Avoid expanding scope until that loop is reliable.
