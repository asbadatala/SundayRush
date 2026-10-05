"""Flatten Yahoo's awkward JSON.

Yahoo's `format=json` mirrors its XML: collections are dicts keyed "0".."n-1" plus "count",
and entities are lists of single-key dicts (sometimes nested lists, sometimes empty lists).
"""

from typing import Any

from app.domain.normalized import (
    NormalizedFantasyTeam,
    NormalizedLeague,
    NormalizedMatchup,
    NormalizedMatchupSide,
    NormalizedRoster,
    NormalizedRosterPlayer,
)

PROVIDER = "yahoo"
BENCH_SLOTS = {"BN"}
IR_SLOTS = {"IR", "IR+", "NA"}


def flatten(node: Any) -> dict[str, Any]:
    """Merge a list of single-key dicts (recursively through nested lists) into one dict."""
    out: dict[str, Any] = {}
    if isinstance(node, dict):
        return dict(node)
    if isinstance(node, list):
        for item in node:
            if isinstance(item, dict):
                out.update(item)
            elif isinstance(item, list):
                out.update(flatten(item))
    return out


def counted(collection: Any, item_key: str) -> list[Any]:
    """Items of a {"0": {item_key: ...}, "1": ..., "count": n} collection, in order."""
    if not isinstance(collection, dict):
        return []
    keys = sorted((k for k in collection if k.isdigit()), key=int)
    return [collection[k][item_key] for k in keys if isinstance(collection[k], dict) and item_key in collection[k]]


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _content(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("fantasy_content") or {}


def _league_from(node: Any) -> NormalizedLeague:
    meta = flatten(node)
    return NormalizedLeague(
        provider=PROVIDER,
        external_league_id=str(meta["league_key"]),
        name=str(meta.get("name") or meta["league_key"]),
        season=int(meta.get("season") or 0),
        current_week=_int(meta.get("current_week")),
        num_teams=_int(meta.get("num_teams")),
        scoring_type=meta.get("scoring_type"),
    )


def parse_leagues(payload: dict[str, Any]) -> list[NormalizedLeague]:
    leagues: list[NormalizedLeague] = []
    for user in counted(_content(payload).get("users"), "user"):
        for game in counted(flatten(user).get("games"), "game"):
            game_meta = flatten(game)
            if game_meta.get("code") not in (None, "nfl"):
                continue
            for league in counted(game_meta.get("leagues"), "league"):
                leagues.append(_league_from(league))
    return leagues


def parse_league(payload: dict[str, Any]) -> NormalizedLeague:
    return _league_from(_content(payload).get("league"))


def _team_meta(team: Any) -> dict[str, Any]:
    # A team is [ [meta single-key dicts...], {stats...}, ... ]
    if isinstance(team, list) and team and isinstance(team[0], list):
        meta = flatten(team[0])
        for extra in team[1:]:
            meta.update(flatten(extra))
        return meta
    return flatten(team)


def _owner(meta: dict[str, Any]) -> tuple[str | None, bool]:
    managers = meta.get("managers") or []
    names: list[str] = []
    is_current = False
    for m in managers:
        manager = m.get("manager") if isinstance(m, dict) else None
        if not manager:
            continue
        if manager.get("nickname") and manager.get("nickname") != "--hidden--":
            names.append(str(manager["nickname"]))
        if str(manager.get("is_current_login", "0")) == "1":
            is_current = True
    return (", ".join(names) or None), is_current


def _team_from(team: Any) -> NormalizedFantasyTeam:
    meta = _team_meta(team)
    owner_name, manager_is_current = _owner(meta)
    owned = str(meta.get("is_owned_by_current_login", "0")) == "1" or manager_is_current
    return NormalizedFantasyTeam(
        provider=PROVIDER,
        external_team_id=str(meta["team_key"]),
        name=str(meta.get("name") or meta["team_key"]),
        owner_name=owner_name,
        is_owned_by_current_user=owned,
    )


def parse_teams(payload: dict[str, Any]) -> list[NormalizedFantasyTeam]:
    league = flatten(_content(payload).get("league"))
    return [_team_from(t) for t in counted(league.get("teams"), "team")]


def _player_from(player: Any) -> NormalizedRosterPlayer:
    meta = flatten(player[0]) if isinstance(player, list) and player and isinstance(player[0], list) else {}
    rest = flatten(player[1:]) if isinstance(player, list) else {}
    selected = flatten(rest.get("selected_position"))
    slot = str(selected.get("position") or "BN")
    name = meta.get("name") or {}
    full_name = name.get("full") if isinstance(name, dict) else str(name)
    position = str(meta.get("primary_position") or meta.get("display_position") or "").split(",")[0]
    is_ir = slot in IR_SLOTS
    is_bench = slot in BENCH_SLOTS or is_ir
    return NormalizedRosterPlayer(
        provider_player_id=str(meta.get("player_id") or str(meta.get("player_key", "")).split(".p.")[-1]),
        full_name=str(full_name or "Unknown player"),
        position=position,
        nfl_team=meta.get("editorial_team_abbr"),
        slot=slot,
        is_starter=not is_bench,
        is_bench=is_bench,
        is_ir=is_ir,
        status=meta.get("status") or None,
    )


def parse_roster(payload: dict[str, Any], week: int) -> NormalizedRoster:
    team = _content(payload).get("team") or []
    meta = flatten(team[0]) if team and isinstance(team[0], list) else {}
    roster = flatten(team[1:]).get("roster") or {}
    players_node = (roster.get("0") or {}).get("players")
    return NormalizedRoster(
        external_team_id=str(meta.get("team_key", "")),
        week=_int(roster.get("week")) or week,
        players=[_player_from(p) for p in counted(players_node, "player")],
    )


def parse_scoreboard(payload: dict[str, Any], week: int) -> list[NormalizedMatchup]:
    league = flatten(_content(payload).get("league"))
    scoreboard = league.get("scoreboard") or {}
    matchups_node = (scoreboard.get("0") or {}).get("matchups")
    out: list[NormalizedMatchup] = []
    for m in counted(matchups_node, "matchup"):
        sides: list[NormalizedMatchupSide] = []
        for t in counted((m.get("0") or {}).get("teams"), "team"):
            meta = _team_meta(t)
            sides.append(
                NormalizedMatchupSide(
                    external_team_id=str(meta["team_key"]),
                    name=str(meta.get("name") or meta["team_key"]),
                    points=_float((meta.get("team_points") or {}).get("total")),
                    projected_points=_float((meta.get("team_projected_points") or {}).get("total")),
                )
            )
        out.append(NormalizedMatchup(week=_int(m.get("week")) or week, status=m.get("status"), teams=sides))
    return out


def parse_settings(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (stat_categories, stat_modifiers) as plain lists of stat dicts."""
    league = flatten(_content(payload).get("league"))
    settings = flatten(league.get("settings"))
    categories = [s["stat"] for s in (settings.get("stat_categories") or {}).get("stats", []) if "stat" in s]
    modifiers = [s["stat"] for s in (settings.get("stat_modifiers") or {}).get("stats", []) if "stat" in s]
    return categories, modifiers
