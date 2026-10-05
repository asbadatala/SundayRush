import type {
  DiscoveredLeague,
  GameDay,
  ImportedLeague,
  League,
  ManualTeam,
  MatchupDetail,
  Matchups,
  Player,
  Preset,
  Provider,
  Team,
} from "./types";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

// The first request mints the anonymous session cookie. Await it once so parallel
// queries on first load don't each create a different anonymous user.
let sessionReady: Promise<void> | null = null;
function ensureSession(): Promise<void> {
  sessionReady ??= fetch("/api/session", { credentials: "same-origin" }).then(
    () => undefined,
    () => {
      sessionReady = null;
    },
  );
  return sessionReady;
}

/** After the server-side session is deleted, the next request must mint a new one. */
export function resetSession() {
  sessionReady = null;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  await ensureSession();
  let resp: Response;
  try {
    resp = await fetch(path, {
      credentials: "same-origin",
      ...init,
      headers: { "content-type": "application/json", ...init.headers },
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "Can't reach the server. Check your connection and try again.", 0);
  }
  const body = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new ApiError(
      body?.code ?? "HTTP_ERROR",
      body?.message ?? `The server returned an error (${resp.status}). Try again in a moment.`,
      resp.status,
    );
  }
  return body as T;
}

const json = (data: unknown) => JSON.stringify(data);
const qs = (params: Record<string, string | number | boolean | undefined>) => {
  const s = new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => [k, String(v)]),
  ).toString();
  return s ? `?${s}` : "";
};

export interface WeekParams {
  season?: number;
  week?: number;
  refresh?: boolean;
}

export const api = {
  gameDay: (p: WeekParams = {}) => request<GameDay>(`/api/game-day${qs({ ...p })}`),
  matchups: (p: WeekParams = {}) => request<Matchups>(`/api/matchups${qs({ ...p })}`),
  matchup: (id: number) => request<MatchupDetail>(`/api/matchups/${id}`),
  nflState: () => request<{ season: number; week: number; season_type: string }>("/api/nfl/state"),

  providers: () => request<Provider[]>("/api/providers"),
  yahooDiscover: () => request<DiscoveredLeague[]>("/api/providers/yahoo/discover", { method: "POST" }),
  yahooDisconnect: () => request<{ deleted: boolean }>("/api/providers/yahoo/connection", { method: "DELETE" }),
  yahooConnectUrl: "/api/providers/yahoo/auth/start",

  leagues: () => request<League[]>("/api/leagues"),
  leagueTeams: (id: number) => request<Team[]>(`/api/leagues/${id}/teams`),
  importLeagues: (leagueIds: string[]) =>
    request<ImportedLeague[]>("/api/leagues/import", {
      method: "POST",
      body: json({ provider: "yahoo", league_ids: leagueIds }),
    }),
  selectTeam: (leagueId: number, teamId: number) =>
    request<League>(`/api/leagues/${leagueId}/select-team`, { method: "POST", body: json({ team_id: teamId }) }),
  refreshLeague: (id: number) => request<League>(`/api/leagues/${id}/refresh`, { method: "POST" }),
  deleteLeague: (id: number) => request<{ deleted: boolean }>(`/api/leagues/${id}`, { method: "DELETE" }),

  searchPlayers: (q: string, signal?: AbortSignal) =>
    request<Player[]>(`/api/players/search${qs({ q })}`, { signal }),

  manualTeams: () => request<ManualTeam[]>("/api/manual-teams"),
  manualTeam: (id: number) => request<ManualTeam>(`/api/manual-teams/${id}`),
  createManualTeam: (body: {
    name: string;
    preset: Preset;
    players: { player_id: number; slot: "starter" | "bench" }[];
  }) => request<ManualTeam>("/api/manual-teams", { method: "POST", body: json(body) }),
  updateManualTeam: (id: number, body: { name?: string; preset?: Preset }) =>
    request<ManualTeam>(`/api/manual-teams/${id}`, { method: "PATCH", body: json(body) }),
  addManualPlayer: (id: number, playerId: number, slot: "starter" | "bench") =>
    request<ManualTeam>(`/api/manual-teams/${id}/players`, {
      method: "POST",
      body: json({ player_id: playerId, slot }),
    }),
  removeManualPlayer: (id: number, playerId: number) =>
    request<ManualTeam>(`/api/manual-teams/${id}/players/${playerId}`, { method: "DELETE" }),
  deleteManualTeam: (id: number) => request<{ deleted: boolean }>(`/api/manual-teams/${id}`, { method: "DELETE" }),

  clearSession: () => request<{ deleted: boolean }>("/api/session", { method: "DELETE" }),
};
