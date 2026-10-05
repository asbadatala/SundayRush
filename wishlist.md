# Owner Wishlist — Research & Scoping

## Context

Spec §30 lists three owner wishlist items that are outside MVP and P1 scope: **betting mode**, a **local sports bar finder**, and **broader AI**. `p1_plan.md` defers all three and says each needs its own design pass. This doc is that pass: it covers research findings, a recommended scope, phases, data model sketches, costs, and risks for each item.

Nothing here is scheduled. Each item becomes a dated `pN_plan.md` phase, plus an ADR in `DECISIONS.md`, once it's picked up.

**How sure the research is (researched 2026-10-04):**
- Many sportsbook-industry and team sites blocked automated fetches.
- Facts confirmed against a fetched source are cited with a URL.
- Items marked **[verify]** come from general knowledge and must be confirmed before building.
- Nothing in the betting section is legal advice. Phase B of betting mode needs a lawyer's opinion.

**Dependencies on P1:**
- All three items need the game-day exposure data that already exists: which of the user's players are in which game, and on which side of each matchup.
- Betting mode and the bar finder use **Phase 6 (Vercel)** for geo headers and shared rate limiting.
- User submissions and saved preferences need **Phase 7 (Google sign-in)**.
- AI builds on the **Phase 8** OpenAI setup: key handling, rate limits, and the spend cap.

---

## Summary

| Item | Recommended first slice | Monthly cost to run | Legal/compliance load | Suggested order |
|---|---|---|---|---|
| Broader AI | "What Matters Right Now?" (deterministic) + weekly recap | Low; model calls with a spend cap | Low (privacy note) | 1st |
| Sports bar finder | Google Places nearby search + our own curated team-affiliation table | ~$0–10 at 1k WAU; ~$1.5k at 10k WAU | Medium (Google terms, location privacy) | 2nd |
| Betting mode | Display-only prop lines, opt-in, 21+, licensed US books, no links | ~$59/mo (The Odds API) | High, and highest for links | 3rd |

**Why this order:** AI has the most product value per unit of risk and reuses existing infrastructure. The bar finder is mostly an integration with a cost and terms constraint. Betting mode is technically simple but carries the most legal and brand risk, and its revenue path (affiliate links) needs a license in each state.

---

## 1. Betting Mode

### What it is (spec §30)
- Opt-in and off by default.
- For each player in the user's fantasy matchups, show player prop lines aligned with the user's fantasy interest:
  - **The user's players:** overs and anytime TD.
  - **Opponents' players:** unders.
- A **hedge** toggle flips both directions.

### Research findings

**Odds data**
- **The Odds API is the best fit** (https://the-odds-api.com/). The 100K-credit plan is $59/mo. Commercial display in an app is allowed, but reselling the raw data is not. Jurisdiction compliance is entirely our responsibility (https://the-odds-api.com/terms-and-conditions.html).
- **Prop markets** (https://the-odds-api.com/sports-odds-data/betting-markets.html):
  - `player_pass_yds`, `player_pass_tds`
  - `player_rush_yds`
  - `player_receptions`, `player_reception_yds`
  - `player_anytime_td`
  - kicker and defensive markets
  - an INT market (likely `player_pass_interceptions` **[verify]**)
- **Cost model:** the event-odds endpoint charges for each market actually returned, per region.
  - 7 markets × 1 region is about 7 credits per game, or about 112 credits to refresh all 16 games once.
  - Hourly refreshes Tuesday to Saturday plus every 15 minutes on game days come to about 45–50K credits a month, which fits the $59 plan.
  - Live in-game polling or a second region would push us to the $119 plan.
- **Deep links:** `includeLinks=true` and `includeSids=true` return bet-slip links or source IDs where a book supports them, at no extra credit cost. Which books actually return them is undocumented, so test on the free tier.
- **Alternatives:**
  - SportsGameOdds: props from $99/mo (https://sportsgameodds.com/pricing/).
  - OpticOdds, Sportradar, SportsDataIO: enterprise pricing.
  - Direct sportsbook affiliate feeds: only available to approved affiliates, who usually need state licensing.
- **Market change:** ESPN Bet no longer exists. ESPN moved to DraftKings as its sportsbook partner in December 2025 (https://en.wikipedia.org/wiki/ESPN_Bet).

**Legal**
- **Showing odds with no links and no payment from a sportsbook** is generally unregulated information; ESPN and newspapers show odds nationwide **[verify]**. Show only **licensed US books**. The Odds API's `us` region includes offshore books (Bovada, BetOnline, MyBookie, BetUS, LowVig), and those must be filtered out.
- **Affiliate or paid links** usually require state vendor or affiliate licensing **[verify per state]**:
  - NJ DGE: vendor registration, or an ancillary license if paid by revenue share.
  - PA PGCB, NY NYSGC (historically CPA or flat fee only, no revenue share), OH OCCC, MA MGC, plus CO, IL, MI and AZ: each has its own rules.
  - Fees run roughly $100 to $5K+ per state, plus background checks on owners.
- **Legal footprint:** about 31 states plus DC have legal online betting **[verify]**. California and Texas don't, which matters for audience size.
- **Age:** treat **21+** as the universal rule. A few states allow 18+.
- **Marketing:** follow the AGA Responsible Marketing Code. That means a 21+ audience, no "risk-free" or "free bet" language, and a helpline on every placement. Several states have written the "risk-free" ban into regulation **[verify]**.
- **Watch list:**
  - Restrictions on props after the 2025 betting scandals. College prop bans already exist in several states, but NFL props are unaffected.
  - The federal SAFE Bet Act; status unknown **[verify]**.
  - The legal fight between states and prediction markets (Kalshi and others); unsettled (https://en.wikipedia.org/wiki/Kalshi).

**Geolocation and age**
- **Display only:** IP-based state detection (Vercel's `x-vercel-ip-country-region` header) plus a self-attested 21+ gate is enough.
- **Affiliate links:** IP state gating so we only link to books licensed in that state. The sportsbook runs GeoComply and KYC when the user bets.
- **GeoComply:** only needed if we took wagers or entries ourselves. That's out of scope.

**Responsible gambling**
- A footer with the helpline for the user's state:
  - National: NCPG **1-800-MY-RESET** (https://www.ncpgambling.org/help-treatment/). 1-800-GAMBLER is still required in NJ, PA and others.
  - NY: 877-8-HOPENY
  - AZ: 1-800-NEXT-STEP
  - MI, MA and CT: state-specific numbers **[verify]**
- A self-exclusion toggle in the app: "hide betting for 30/90/365 days / permanently", deliberately hard to undo.
- Links to state self-exclusion programs. We can't check the state lists ourselves.
- No streaks and no "you would have won $X" messages.

**Platform constraints**
- **Vercel:** its acceptable use policy only bans unlawful use.
- **Google Play:** this is the biggest constraint for a native app. Play's policy bans gambling "companion functionality" and gives an odds tracker with sportsbook links as an example violation (https://support.google.com/googleplay/android-developer/answer/9877032). A native Android app would have to ship without links, or go through Play's real-money gambling program.
- **Apple:** odds-display apps are generally allowed. Apps that facilitate betting fall under guidelines 1.4 and 5.3 **[verify]**.
- **Google Ads:** gambling ads need certification and state targeting (https://support.google.com/adspolicy/answer/6018017).

**Precedent:** ESPN Fantasy shows DraftKings odds, Yahoo Fantasy has BetMGM modules, and Action Network is a licensed affiliate with state-gated bet-slip links. Mixing fantasy and betting is normal. Regulators do pay attention to under-21 audiences, and fantasy audiences skew young.

### Mapping props to fantasy interest

| Prop | Fantasy stat | Direction for the user's player (hedge off) |
|---|---|---|
| Pass yds / Rush yds / Rec yds | yards | over |
| Receptions | receptions (PPR) | over |
| Pass TDs | pass TD | over |
| Anytime TD | rush/rec TD | yes |
| **Interceptions** | INT (negative points) | **under** (inverted) |

- **Opponents' players:** use the opposite direction.
- **Hedge on:** flips both sides.
- **Anytime TD:** most books have no "under", so show "No" if a book offers it and skip it otherwise.
- **Store direction per market** (`direction_for_owner`), not as one global "over" rule, so inverted stats like INTs are correct.
- **Scoring weighting:** a later improvement is to weight props by the user's league scoring. In PPR, receptions matter more.

### Recommended scope

**Phase A: display only (recommended first slice)**
- Settings toggle, off by default. Turning it on requires 21+ self-attestation.
- Shown only when the user's IP state has legal online betting. That isn't strictly required for display, but it lowers risk and keeps the UI honest.
- Prop lines appear inline on player rows and matchup detail as "market line" chips, never as recommendations. Avoid words like "lock", "free" and "best bet".
- Licensed US books only (DraftKings, FanDuel, BetMGM, Caesars, Fanatics), filtered by an allowlist.
- No links and no revenue.
- Responsible-gambling footer plus the self-exclusion toggle.
- **Deliverable:** a user in a legal state who opts in sees aligned prop lines for every rostered player in their matchups.

**Phase B: affiliate links (gated on a lawyer's opinion and licensing)**
- Join DraftKings and FanDuel affiliate programs. Use The Odds API links/SIDs for bet-slip deep links.
- Register as a vendor/affiliate state by state, starting with the biggest markets (NJ, PA, NY, OH, MI, IL, AZ).
- Show only the books licensed in the user's state.
- Build marketing to the AGA code.
- **Decision gate:** this is the only part of the wishlist that makes money directly, and the only part with real regulatory overhead.

**Phase C: prediction markets.** On hold until the legal fight between states and the CFTC settles.

### Data model sketch
```
prop_market(id, provider_key, normalized_stat_key, direction_for_owner ENUM('over','under','yes'))
prop_line(id, nfl_game_id, canonical_player_id, market_id, bookmaker_key,
          line NUMERIC NULL, over_price INT, under_price INT,
          link TEXT NULL, sid TEXT NULL, fetched_at)        -- idx (nfl_game_id, canonical_player_id, market_id)
betting_preferences(user_id, enabled BOOL DEFAULT false, age_attested_at, hedge BOOL,
                    preferred_books TEXT[], excluded_until TIMESTAMPTZ NULL)
odds_poll_log(run_at, events_polled, credits_used, credits_remaining)   -- from x-requests-remaining
```
- Odds are global, so fetch once and share across all users. Poll only games that contain rostered players.
- **The biggest engineering task is resolving player names.** The Odds API keys props by player name, not ID, so they go through `PlayerResolver` (ADR-005) restricted to the game's two teams. Results are written to `player_id_mapping` with `provider='the_odds_api'`.
- The polling job runs as a Vercel Cron Job. Hobby crons run at most once a day, so game-day frequency needs Pro or polling triggered when users load data.
- The API side follows `NFLDataProvider`-style boundaries: an `OddsProvider` interface with a single The Odds API implementation.

### Risks
- An audience that skews under 21, and the brand risk of a "fantasy app pushes bets" story.
- Accidentally showing offshore books. The allowlist is a hard requirement.
- Google Play blocking a native Android app.
- State rules on props and prediction markets changing quickly.
- API cost jumping if live in-game odds are added.

### Open questions for the owner
1. Is Phase A (no revenue) worth shipping on its own, or is betting mode only worth doing if Phase B monetizes it?
2. Hide the feature entirely in non-legal states, or show odds everywhere as information?
3. Which books should be the default?

---

## 2. Local Sports Bar Finder

### What it is (spec §30)
- With the user's permission, suggest nearby sports bars to watch the games.
- Show each bar's team affiliation where one exists (e.g. a known Giants bar).

### Research findings

**Place data**

| Source | Sports-bar signal | Price | Terms that matter |
|---|---|---|---|
| **Google Places API (New)** | `sports_bar` type, `goodForWatchingSports` attribute | Nearby Search Pro $32/1k (5k free/mo); Enterprise $35/1k; +Atmosphere $40/1k (1k free/mo). Text Search "IDs Only" is **free and unlimited**. | `place_id` can be stored forever. Other content can't be cached server-side (lat/lng up to 30 days **[verify]**). Google Maps attribution is required. |
| Apple MapKit JS / Maps Server API | No sports-bar category; search the text "sports bar" | 25k calls/day free with the $99/yr developer program | Display requirements **[verify]** |
| Foursquare | "Sports Bar" category **[verify]** | 500 free calls, then $15/1k | — |
| Yelp Places API | `sportsbars` category **[verify]** | $229/mo minimum | 24-hour storage limit, and you can't build your own business database from it. **Poor fit.** |
| Mapbox Search | Thin POI data **[verify]** | 50k/mo free | — |
| OpenStreetMap | `sport=*` means *playing* a sport, not TVs showing games | Free | ODbL share-alike applies to a merged database. Fallback only. |

Sources: https://developers.google.com/maps/billing-and-pricing/pricing, https://developers.google.com/maps/documentation/places/web-service/policies, https://business.yelp.com/data/resources/pricing/, https://foursquare.com/pricing/, https://developer.apple.com/maps/web/

- **Google wins on data quality**, but its terms rule out a shared server cache of names, ratings or hours across users. Every search is billed.
- Nearby Search returns at most 20 results per request, with no pagination and a radius up to 50 km.
- The most expensive field requested sets the price, so keep search requests to Pro fields and load hours and rating only when a card is tapped.

**Team-affiliation data**
- **Official fan-club networks exist.** For example, Bills Backers has 600+ chapters on a YinzCam-hosted map (https://www.buffalobills.com/fans/bills-backers). Other teams' programs exist, but their URLs and formats are **[verify]**.
- **Don't scrape.** NFL.com's terms ban systematic retrieval to build a database or directory (https://www.nfl.com/legal/terms), and team sites are probably similar.
- **Practical approach:** keep a **curated affiliation table we own**:
  - seed it by hand from public knowledge;
  - ask fan clubs for permission or partnerships;
  - add user submissions and bar-owner claims.
- Match each bar to a Google `place_id` with the free IDs-only Text Search and store it forever. Affiliation data is ours, so caching limits don't apply to it.

**"Will this bar show my game?"**
- Commercial NFL Sunday Ticket goes only through EverPass Media, which has **no public venue locator** (https://www.everpass.com/live-sports/nfl-sunday-ticket/). No dataset of Sunday Ticket bars exists.
- Realistic approach:
  - A "likely needs Sunday Ticket" label on out-of-market Sunday afternoon games, since local CBS/FOX and national NBC/ESPN/Prime games are watchable anywhere. The source for broadcast maps is **[verify]**, and its licensing is unknown.
  - A **fan-reported** "has Sunday Ticket" flag on bars.

**Location privacy**
- **CPRA:** "precise geolocation" (within 1,850 ft) is sensitive personal information (https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.140).
- **Virginia** (1,750 ft) and similar state laws require **opt-in** consent for it (https://law.lis.virginia.gov/vacode/title59.1/chapter53/section59.1-575/). SundayRush may be under these laws' size thresholds, but designing as if they apply is cheap.
- **Design:**
  - Show an in-app explanation before the browser permission prompt.
  - Use `enableHighAccuracy:false`.
  - **Round coordinates on the client** to 2 decimal places (about 1.1 km) before sending.
  - Never store or log raw coordinates.
  - If a home area is saved, store it as a ZIP code or 5-character geohash, and only with consent.
- **Fallbacks:**
  - Vercel's `x-vercel-ip-latitude`/`-longitude`/`-postal-code` headers give a rough default with no prompt (https://vercel.com/docs/headers/request-headers).
  - Typed ZIP code entry.

### Ranking
The score combines:
1. **Affiliation boost** when the bar's team matches the user's favorite team, or the team with the most fantasy exposure in that kickoff window. The app already computes exposure per game.
2. **Open at kickoff**, from `currentOpeningHours`; this needs the Details call.
3. Distance decay.
4. Rating × log(review count).
5. Bonuses for `primaryType=sports_bar`, `goodForWatchingSports`, and a confirmed Sunday Ticket flag.

Every card shows *why* it ranked, e.g. "Giants bar · 3 of your starters play in NYG–DAL". That reason is SundayRush's edge over Google Maps.

The spec's open question was whether to rank by fantasy exposure or by favorite team. **Recommendation: both.** Use the favorite team as an explicit preference and fantasy exposure as the default when no favorite is set.

### Recommended scope

**Phase A: MVP**
- A "Where to watch" entry from the Games tab (no new bottom-nav tab, per spec §9's small-navigation rule).
- Location comes from the IP default, a typed ZIP, or an opt-in browser location rounded on the client.
- `POST /api/bars/search` calls Google Nearby Search with `includedPrimaryTypes:[sports_bar]` (falling back to `bar`/`pub`), a radius of about 8 km, and **Pro fields only**.
- Tapping a card fetches Place Details for hours and rating.
- Results are merged with the curated `bar_affiliation` table by `place_id`.
- Google Maps attribution is shown. "Open in Maps" uses the **free** Maps Embed API or a plain Maps URL.
- Abuse controls: per-session and per-IP rate limits (Upstash, P1 Phase 6), a Google Cloud quota cap, and budget alerts.
- **Deliverable:** a user sees nearby sports bars ranked by relevance to their Sunday, with team-affiliated bars labeled.

**Phase B: community data** (needs Google sign-in)
- Signed-in users can submit affiliations and features.
- A corroboration count ("3 fans confirm") and admin approval.
- Fan-reported entries expire after one season unless reconfirmed.
- Bar owners can claim their listing.
- A fan-reported Sunday Ticket flag.

**Phase C: later**
- Atmosphere fields (`goodForWatchingSports`).
- Watch-party check-ins.
- Fan-club partnerships.
- An Apple Maps fallback to cut cost at scale.

### Cost estimate
Assumptions: 60% of weekly active users open the finder about twice a week, which is about 5.2 searches per user per month. There is no shared cache (Google terms).

| WAU | Searches/mo | Search cost (Pro fields) |
|---|---|---|
| 1k | ~5.2k | **~$6** (mostly within the 5k free tier) |
| 10k | ~52k | **~$1,500** |

- Taps that load details add about $17–20 per 1k taps.
- At 10k WAU, testing a hybrid of Apple search results plus our affiliation table is worth it. That would cost about $0, but with a weaker sports-bar signal.

### Data model sketch
```
bar_affiliation(id, google_place_id UNIQUE, team_abbr,
                kind ENUM('official_chapter','fan_reported','owner_claimed'),
                source_url NULL, status ENUM('pending','approved','rejected'),
                confirmations INT, season INT, created_by NULL, created_at)
bar_feature(google_place_id, feature ENUM('sunday_ticket','sound_on',...), season, confirmations, status)
bar_submission(id, user_id, payload JSONB, status, reviewer_id NULL, reviewed_at NULL)
user_preferences.location_area   -- optional ZIP or geohash5 with consented_at; never raw coordinates
```
Store our own name and city on curated rows only. Never persist Google content beyond `place_id`.

### Risks
- Breaking Google's terms through shared caching or missing attribution.
- Cost spikes from bots, mitigated by rate limits, quota caps and the Vercel firewall.
- Few affiliated bars outside big metros at launch, so the curated seed list matters.
- Affiliation spam or stale data, handled by moderation and seasonal expiry.
- Implying a bar shows a specific game. Always label it "fan-reported".

### Open questions for the owner
1. Should SundayRush collect a **favorite NFL team** for ranking, or rely on fantasy exposure only?
2. How much manual curation are you willing to do for the seed list, and for which metros first?

---

## 3. Broader AI

> **Not yet researched externally.** The research pass for this item was stopped before it finished. This section is scoped from the existing spec and P1 plan. Competitor features, current model pricing, and news-data licensing still need research before it becomes a plan.

### Constraints from the spec
- The product is a "game-day companion, **not an AI fantasy advisor**" (spec §28). AI start/sit, trade analysis, waiver recommendations and expert rankings are MVP non-goals (spec §8).
- Already planned:
  - Screenshot roster import (P1 Phase 8, OpenAI, ADR-015).
  - AI game-day summaries and a voice assistant (spec §7, P2).
  - "What Matters Right Now?" (spec §30).

### Guiding principle: the engine computes, the model only phrases
- Every number shown to the user comes from the scoring engine, matchup service or projections, never from the model.
- The model gets a small structured *facts* payload (computed margins, remaining players, points needed) and only turns it into prose or answers questions using tools.
- This keeps hallucination risk low, makes outputs testable against fixtures, and fits the existing architecture.

### Candidate use cases

| # | Use case | How it works | Needs outside news? | Advisor conflict? | Recommendation |
|---|---|---|---|---|---|
| 1 | **What Matters Right Now?** | Deterministic: per matchup, compute margin, remaining starters per side, and points needed (actual + projected), then rank games by impact. Optional LLM one-liners. | No | No | **Tier 1.** Mostly not AI; ship the deterministic version first. |
| 2 | **Weekly recap per league** | After Monday night: facts (result, top scorer, bench points left behind, closest finish) → LLM recap. Cache per (league, week). Shareable card. | No | No | **Tier 1** |
| 3 | **Live game-day digest** | At halftime or the end of each window: "You're up in 3 of 4; DAL–HOU decides League B." Same facts as #1. | No | No | Tier 1.5; pairs with P2 notifications |
| 4 | **Natural-language Q&A over your own data** | Tool calling against existing services (`game_day`, `matchups`, `standings`): "Which of my players are still playing?" "How many does Kelce need?" | No | Low, if questions are scoped to the user's own data | **Tier 2** |
| 5 | Injury/news impact explanations | Explain why a player is out and what it means | **Yes**; needs a licensed news source | Medium | Tier 3; blocked on a news source |
| 6 | Win probability + explanation | A statistical model from projections and remaining players, with the LLM explaining it | No | Low | Tier 2; the probability model is the real work, not the LLM |
| 7 | Trash-talk / smack-talk generator | Facts from the matchup → playful message to copy | No | No | Fun, cheap, viral; Tier 2 |
| 8 | Voice mode | Speech in → #4 → speech out | No | Low | Tier 3 (spec P2) |
| 9 | Start/sit and lineup advice | — | Yes | **Yes** | **Keep as a non-goal** unless the owner changes positioning |

### Architecture notes
- **Provider:** reuse the Phase 8 OpenAI setup (`OPENAI_API_KEY`, the model as config, rate limits, daily spend cap). Put a thin `LLMClient` interface in front of it so the model or provider can change without touching features. Compare current OpenAI and Anthropic models on tool calling, structured outputs, latency and price when the work starts. **[research pending]**
- **Facts layer:** a pure-Python `insights/` package builds typed facts from existing services. It's unit-testable without any model.
- **Caching:** key by (league, week, hash of the facts). Recaps are generated once. Live digests regenerate only when the facts change.
- **Streaming:** Q&A streams over SSE from FastAPI, behind the existing Next rewrite. Check Vercel function duration limits.
- **Safety:**
  - Team and player names imported from leagues are user-controlled text, so treat them as data, not instructions. They go in a delimited facts block and get no tool-execution power.
  - Tools are read-only and scoped to the session's `user_id`.
- **Privacy:** league and team names go to the model provider. Add this to the Settings privacy note next to the screenshot disclosure.
- **Evals:** golden fact fixtures in `FIXTURE_MODE`, with recorded model responses in CI (no live calls), as in Phase 8. A check fails if any number in the output isn't in the facts.

### Recommended roadmap
1. **What Matters Right Now? (deterministic).** A banner or card at the top of Games. **Metric:** share of game-day sessions that interact with it.
2. **Weekly recap.** On Matchups after the week ends, with a share image. **Metric:** recap views and shares per league per week.
3. **Live digest.** Ships with the P2 notifications work. **Metric:** notification opt-in and open rate.
4. **Q&A over your own data.** **Metric:** answered without fallback; zero numeric mismatches in evals.
5. **Later:** win probability, smack-talk generator, voice.

### Open questions for the owner
1. Keep "not an advisor" as a firm line, or is start/sit help something you'd actually want later?
2. Which matters more to you first: the live "what matters" view or the shareable weekly recap?
3. Should the AI research pass be rerun (competitors, model costs, news licensing) before this becomes a plan?

---

## Owner decisions needed

| # | Question | Item |
|---|---|---|
| W1 | Build order: AI → bar finder → betting? | All |
| W2 | Is display-only betting worth shipping without affiliate revenue? | Betting |
| W3 | Hide betting entirely outside legal states? | Betting |
| W4 | Collect a favorite NFL team? | Bar finder (also useful elsewhere) |
| W5 | Commit time to curating the bar affiliation seed list? | Bar finder |
| W6 | Keep start/sit as a permanent non-goal? | AI |

Once these are answered, record them as ADRs and move the chosen slices into the next phase plan.
