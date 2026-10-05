"""Manual (custom) teams. Rosters are user-entered and already canonical, so they are written
straight into the same normalized tables (FantasyTeam/RosterSnapshot/RosterEntry) imported
teams use; everything downstream treats them identically."""

from sqlmodel import Session, col, select

from app.domain.models import CanonicalPlayer, FantasyTeam, RosterEntry, RosterSnapshot, ScoringProfile, User, utcnow
from app.errors import NotFound, ValidationFailed
from app.scoring.presets import PRESET_LABELS, preset_rules

PROVIDER = "manual"


def get_manual_team(db: Session, user: User, team_id: int) -> FantasyTeam:
    team = db.get(FantasyTeam, team_id)
    if team is None or team.user_id != user.id or not team.is_manual:
        raise NotFound("That custom team doesn't exist.")
    return team


def latest_snapshot(db: Session, team_id: int) -> RosterSnapshot | None:
    return db.exec(
        select(RosterSnapshot)
        .where(RosterSnapshot.fantasy_team_id == team_id)
        .order_by(col(RosterSnapshot.season).desc(), col(RosterSnapshot.week).desc())
    ).first()


def create_manual_team(db: Session, user: User, name: str, preset: str, season: int, week: int) -> FantasyTeam:
    if preset not in PRESET_LABELS:
        raise ValidationFailed(f"Unknown scoring preset '{preset}'.")
    profile = ScoringProfile(
        user_id=user.id, name=PRESET_LABELS[preset], preset=preset, scoring_json=preset_rules(preset).rules
    )
    db.add(profile)
    db.flush()
    team = FantasyTeam(
        user_id=user.id,
        provider=PROVIDER,
        name=name.strip(),
        is_user_team=True,
        is_manual=True,
        scoring_profile_id=profile.id,
    )
    db.add(team)
    db.flush()
    assert team.id is not None
    db.add(RosterSnapshot(fantasy_team_id=team.id, season=season, week=week))
    db.commit()
    db.refresh(team)
    return team


def update_manual_team(db: Session, team: FantasyTeam, name: str | None, preset: str | None) -> FantasyTeam:
    if name is not None:
        if not name.strip():
            raise ValidationFailed("Team name can't be empty.")
        team.name = name.strip()
    if preset is not None:
        if preset not in PRESET_LABELS:
            raise ValidationFailed(f"Unknown scoring preset '{preset}'.")
        profile = db.get(ScoringProfile, team.scoring_profile_id) if team.scoring_profile_id else None
        if profile is None:
            profile = ScoringProfile(user_id=team.user_id, name="", scoring_json={})
        profile.name = PRESET_LABELS[preset]
        profile.preset = preset
        profile.scoring_json = preset_rules(preset).rules
        db.add(profile)
        db.flush()
        team.scoring_profile_id = profile.id
    team.updated_at = utcnow()
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def add_player(db: Session, team: FantasyTeam, player_id: int, slot: str) -> RosterEntry:
    if slot not in ("starter", "bench"):
        raise ValidationFailed("Slot must be 'starter' or 'bench'.")
    player = db.get(CanonicalPlayer, player_id)
    if player is None:
        raise NotFound("That player doesn't exist.")
    assert team.id is not None
    snapshot = latest_snapshot(db, team.id)
    if snapshot is None:
        raise NotFound("Custom team roster is missing.")
    existing = db.exec(
        select(RosterEntry).where(RosterEntry.roster_snapshot_id == snapshot.id, RosterEntry.player_id == player_id)
    ).first()
    entry = existing or RosterEntry(roster_snapshot_id=snapshot.id or 0, player_id=player_id, slot="")
    entry.slot = player.position if slot == "starter" else "BN"
    entry.is_starter = slot == "starter"
    entry.is_bench = slot == "bench"
    db.add(entry)
    snapshot.fetched_at = utcnow()
    db.add(snapshot)
    db.commit()
    db.refresh(entry)
    return entry


def remove_player(db: Session, team: FantasyTeam, player_id: int) -> None:
    assert team.id is not None
    snapshot = latest_snapshot(db, team.id)
    if snapshot is None:
        return
    entry = db.exec(
        select(RosterEntry).where(RosterEntry.roster_snapshot_id == snapshot.id, RosterEntry.player_id == player_id)
    ).first()
    if entry is None:
        raise NotFound("That player isn't on this team.")
    db.delete(entry)
    db.commit()
