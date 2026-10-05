// Mirrors the FastAPI response models (apps/api/app/**/schemas + routers).

export type Ownership = "MY_STARTER" | "MY_BENCH" | "OPPONENT";
export type GameStatus =
  | "scheduled"
  | "pregame"
  | "live"
  | "halftime"
  | "final"
  | "postponed"
  | "canceled";

export interface Game {
  id: number;
  external_game_id: string;
  kickoff_at: string;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  status: GameStatus;
  status_detail: string | null;
  quarter: number | null;
  clock: string | null;
  broadcaster: string | null;
}

export interface PlayerRow {
  key: string;
  player_id: number | null;
  name: string;
  position: string;
  nfl_team: string | null;
  league_id: number | null;
  league_name: string;
  team_id: number;
  team_name: string;
  provider: string;
  ownership: Ownership;
  slot: string;
  points: number | null;
  points_unavailable_reason: string | null;
  injury_status: string | null;
  stat_line: string | null;
  mapped: boolean;
  game_id: number | null;
  game_status: GameStatus | null;
}

export interface PlayerGroups {
  my_starters: PlayerRow[];
  my_bench: PlayerRow[];
  opponents: PlayerRow[];
}

export interface GameGroup extends PlayerGroups {
  game: Game;
}

export interface LeagueError {
  league_id: number | null;
  league_name: string;
  provider: string;
  code: string;
  message: string;
}

export interface GameDay {
  season: number;
  week: number;
  generated_at: string;
  stats_as_of: string | null;
  live_data_available: boolean;
  any_live: boolean;
  has_teams: boolean;
  team_count: number;
  games: GameGroup[];
  no_game: PlayerGroups;
  league_errors: LeagueError[];
}

export interface MatchupSide {
  team_id: number | null;
  name: string;
  owner_name: string | null;
  score: number | null;
  projected: number | null;
}

export interface MatchupCard {
  id: number | null;
  league_id: number | null;
  league_name: string;
  provider: string;
  week: number;
  status: string | null;
  has_matchup: boolean;
  my_team: MatchupSide;
  opponent: MatchupSide | null;
}

export interface Matchups {
  season: number;
  week: number;
  matchups: MatchupCard[];
  league_errors: LeagueError[];
}

export interface MatchupDetail {
  card: MatchupCard;
  my_starters: PlayerRow[];
  opponent_starters: PlayerRow[];
  my_engine_total: number;
  opponent_engine_total: number;
}

export interface Provider {
  id: string;
  name: string;
  available: boolean;
  connected: boolean;
  connected_at: string | null;
  note: string | null;
}

export interface Team {
  id: number;
  external_team_id: string | null;
  name: string;
  owner_name: string | null;
  is_user_team: boolean;
}

export interface League {
  id: number;
  provider: string;
  external_league_id: string;
  name: string;
  season: number;
  current_week: number | null;
  num_teams: number | null;
  selected_team_id: number | null;
  selected_team_name: string | null;
  last_synced_at: string | null;
  scoring_name: string | null;
  scoring_rules: Record<string, number>;
  unsupported_scoring: { stat_id: number; name: string | null; reason: string }[];
}

export interface DiscoveredLeague {
  external_league_id: string;
  name: string;
  season: number;
  num_teams: number | null;
  scoring_type: string | null;
  imported_league_id: number | null;
}

export interface ImportedLeague {
  league: League;
  teams: Team[];
  suggested_team_id: number | null;
}

export interface Player {
  id: number;
  full_name: string;
  position: string;
  nfl_team: string | null;
  active_status: string | null;
  injury_status: string | null;
}

export type Preset = "standard" | "half_ppr" | "ppr";

export interface ManualTeam {
  id: number;
  name: string;
  preset: Preset | null;
  scoring_name: string | null;
  updated_at: string;
  starters: { player: Player; slot: string; is_starter: boolean }[];
  bench: { player: Player; slot: string; is_starter: boolean }[];
}
