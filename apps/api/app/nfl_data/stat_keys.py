"""Sleeper stat field -> normalized stat key.

Normalized keys are canonical and non-overlapping, so the scoring engine never double counts
(e.g., there is no combined "total yards" key alongside rush and receiving yards).
Several Sleeper fields can feed one normalized key; values are summed.
"""

SLEEPER_TO_NORMALIZED: dict[str, str] = {
    # Passing
    "pass_att": "pass_att",
    "pass_cmp": "pass_cmp",
    "pass_inc": "pass_inc",
    "pass_yd": "pass_yards",
    "pass_td": "pass_td",
    "pass_int": "interception",
    "pass_sack": "pass_sack",
    # Rushing
    "rush_att": "rush_att",
    "rush_yd": "rush_yards",
    "rush_td": "rush_td",
    # Receiving
    "rec_tgt": "target",
    "rec": "reception",
    "rec_yd": "receiving_yards",
    "rec_td": "receiving_td",
    # Misc offense
    "fum": "fumble",
    "fum_lost": "fumble_lost",
    "pass_2pt": "two_pt",
    "rush_2pt": "two_pt",
    "rec_2pt": "two_pt",
    "kr_td": "return_td",
    "pr_td": "return_td",
    "kr_yd": "return_yards",
    "pr_yd": "return_yards",
    "fum_rec_td": "fumble_rec_td",
    # Kicking (stored for display; K scoring is deferred)
    "fgm": "fg_made",
    "fga": "fg_att",
    "fgm_0_19": "fg_made_0_19",
    "fgm_20_29": "fg_made_20_29",
    "fgm_30_39": "fg_made_30_39",
    "fgm_40_49": "fg_made_40_49",
    "fgm_50p": "fg_made_50_plus",
    "fgmiss": "fg_miss",
    "xpm": "xp_made",
    "xpmiss": "xp_miss",
    # Team defense (stored for display; DEF scoring is deferred)
    "sack": "def_sack",
    "int": "def_interception",
    "fum_rec": "def_fumble_recovery",
    "def_td": "def_td",
    "safe": "def_safety",
    "blk_kick": "def_block_kick",
    "pts_allow": "def_points_allowed",
    "yds_allow": "def_yards_allowed",
}


def normalize_sleeper_stats(raw: dict[str, float | int | None]) -> dict[str, float]:
    out: dict[str, float] = {}
    for src, dst in SLEEPER_TO_NORMALIZED.items():
        value = raw.get(src)
        if value is None:
            continue
        out[dst] = round(out.get(dst, 0.0) + float(value), 4)
    return out
