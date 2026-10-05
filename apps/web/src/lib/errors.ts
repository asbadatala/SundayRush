// Actionable copy for error codes that arrive via redirects (query string) rather than JSON.
export const ERROR_COPY: Record<string, string> = {
  PROVIDER_AUTH_REQUIRED: "Yahoo sign-in was cancelled. Try again, or create a custom team instead.",
  PROVIDER_AUTH_EXPIRED: "Your Yahoo connection has expired. Reconnect Yahoo, or create a custom team instead.",
  OAUTH_STATE_INVALID: "That Yahoo sign-in link expired or was already used. Start the connection again.",
  PROVIDER_UNAVAILABLE: "Yahoo isn't available right now. Try again shortly, or create a custom team instead.",
};

export function errorCopy(code: string | null | undefined): string | null {
  if (!code) return null;
  return ERROR_COPY[code] ?? "Something interrupted the connection. Try again, or create a custom team instead.";
}
