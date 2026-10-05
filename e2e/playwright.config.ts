import { defineConfig, devices } from "@playwright/test";

// Full stack with FIXTURE_MODE=1: recorded ESPN/Sleeper data + a fake Yahoo OAuth/API.
// The E2E database is rebuilt from migrations on every run.
const API_PORT = 8011;
const WEB_PORT = 3111;
const DATABASE_URL =
  process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://sundayrush:sundayrush@localhost:5442/sundayrush_e2e";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "mobile", use: { ...devices["Pixel 7"] } },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } },
  ],
  webServer: [
    {
      command: `uv run alembic downgrade base && uv run alembic upgrade head && uv run uvicorn app.main:app --port ${API_PORT}`,
      cwd: "../apps/api",
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      env: {
        DATABASE_URL,
        FIXTURE_MODE: "1",
        COOKIE_SECURE: "false",
        LOG_LEVEL: "WARNING",
        RATE_LIMIT_IMPORT: "1000/minute",
        RATE_LIMIT_SEARCH: "1000/minute",
      },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      // Production build: realistic, and no dev overlay covering the mobile bottom nav.
      // API_URL is baked into the rewrites at build time.
      command: `pnpm build && pnpm start --port ${WEB_PORT}`,
      cwd: "../apps/web",
      url: `http://localhost:${WEB_PORT}`,
      env: { API_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: !process.env.CI,
      timeout: 240_000,
    },
  ],
});
