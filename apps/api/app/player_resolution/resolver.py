"""Provider player -> canonical player (spec §20).

Priority:
  1. player_id_mapping (provider, external_id)
  2. canonical provider id column (e.g. yahoo_id)
  3. exact normalized name + NFL team + position
  4. rapidfuzz fallback, accepted only at >= FUZZY_THRESHOLD and logged
Team defenses resolve by NFL team. Results are written back to player_id_mapping.
"""

from dataclasses import dataclass

from rapidfuzz import fuzz, process
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.domain.models import CanonicalPlayer, PlayerIdMapping
from app.logging import log
from app.nfl_data.teams import normalize_team
from app.player_resolution.names import normalize_name

FUZZY_THRESHOLD = 0.92
PROVIDER_ID_COLUMNS = {"yahoo": "yahoo_id", "espn": "espn_id", "sleeper": "sleeper_id"}
DEF_POSITIONS = {"DEF", "DST", "D/ST"}


@dataclass
class PlayerRef:
    provider: str
    external_id: str
    full_name: str
    position: str
    nfl_team: str | None


@dataclass
class Resolution:
    player_id: int | None
    method: str | None
    confidence: float


def best_fuzzy(name: str, candidates: dict[int, str]) -> tuple[int, float] | None:
    """Return (player_id, score 0..1) of the best candidate, or None."""
    if not candidates:
        return None
    match = process.extractOne(normalize_name(name), candidates, scorer=fuzz.ratio)
    if match is None:
        return None
    _, score, player_id = match
    return int(player_id), score / 100.0


class PlayerResolver:
    def __init__(self, session: Session):
        self.session = session

    def resolve(self, ref: PlayerRef) -> Resolution:
        position = "DEF" if ref.position.upper() in DEF_POSITIONS else ref.position.upper()
        team = normalize_team(ref.nfl_team)

        mapped = self.session.exec(
            select(PlayerIdMapping).where(
                PlayerIdMapping.provider == ref.provider, PlayerIdMapping.external_id == ref.external_id
            )
        ).first()
        if mapped:
            return Resolution(mapped.player_id, "mapping", mapped.confidence)

        resolution = self._resolve_uncached(ref, position, team)
        if resolution.player_id is not None and resolution.method is not None:
            self._save(ref, resolution)
        else:
            log.warning(
                "PLAYER_MAPPING_FAILED",
                provider=ref.provider,
                external_id=ref.external_id,
                name=ref.full_name,
                position=position,
                team=team,
            )
        return resolution

    def _resolve_uncached(self, ref: PlayerRef, position: str, team: str | None) -> Resolution:
        id_col = PROVIDER_ID_COLUMNS.get(ref.provider)
        if id_col:
            by_id = self.session.exec(
                select(CanonicalPlayer.id).where(getattr(CanonicalPlayer, id_col) == ref.external_id)
            ).first()
            if by_id is not None:
                return Resolution(by_id, "provider_id", 1.0)

        if position == "DEF":
            if team:
                def_id = self.session.exec(
                    select(CanonicalPlayer.id).where(
                        CanonicalPlayer.position == "DEF", CanonicalPlayer.nfl_team_code == team
                    )
                ).first()
                if def_id is not None:
                    return Resolution(def_id, "exact", 1.0)
            return Resolution(None, None, 0.0)

        normalized = normalize_name(ref.full_name)
        exact_q = select(CanonicalPlayer.id).where(
            CanonicalPlayer.normalized_name == normalized, CanonicalPlayer.position == position
        )
        if team:
            exact_q = exact_q.where(CanonicalPlayer.nfl_team_code == team)
        exact = list(self.session.exec(exact_q).all())
        if len(exact) == 1:
            return Resolution(exact[0], "exact", 1.0)
        if team and not exact:
            # Recently traded/released players: unique name + position match across all teams.
            anywhere = list(
                self.session.exec(
                    select(CanonicalPlayer.id).where(
                        CanonicalPlayer.normalized_name == normalized, CanonicalPlayer.position == position
                    )
                ).all()
            )
            if len(anywhere) == 1:
                return Resolution(anywhere[0], "exact", 0.95)

        # Fuzzy: same position, prefer same team; widen to position-only when team is unknown.
        fuzzy_q = select(CanonicalPlayer.id, CanonicalPlayer.normalized_name).where(
            CanonicalPlayer.position == position
        )
        if team:
            fuzzy_q = fuzzy_q.where(CanonicalPlayer.nfl_team_code == team)
        candidates = {pid: name for pid, name in self.session.exec(fuzzy_q).all() if pid is not None}
        best = best_fuzzy(ref.full_name, candidates)
        if best and best[1] >= FUZZY_THRESHOLD:
            log.info(
                "player_fuzzy_match",
                provider=ref.provider,
                external_id=ref.external_id,
                name=ref.full_name,
                player_id=best[0],
                score=round(best[1], 3),
            )
            return Resolution(best[0], "fuzzy", round(best[1], 3))
        return Resolution(None, None, best[1] if best else 0.0)

    def _save(self, ref: PlayerRef, resolution: Resolution) -> None:
        stmt = insert(PlayerIdMapping).values(
            provider=ref.provider,
            external_id=ref.external_id,
            player_id=resolution.player_id,
            method=resolution.method,
            confidence=resolution.confidence,
        )
        self.session.execute(stmt.on_conflict_do_nothing(index_elements=["provider", "external_id"]))


def get_players_by_ids(session: Session, ids: set[int]) -> dict[int, CanonicalPlayer]:
    if not ids:
        return {}
    return {p.id: p for p in session.exec(select(CanonicalPlayer).where(col(CanonicalPlayer.id).in_(ids)))}  # type: ignore[misc]
