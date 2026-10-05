import { expect, test } from "@playwright/test";

import { connectYahooAndImport, expectNoHorizontalScroll, gameCard } from "./helpers";

test("1–4: first-time user connects Yahoo, picks teams, and sees relevant games", async ({ page }) => {
  await connectYahooAndImport(page);

  await expect(page.getByRole("heading", { name: "Week 4" })).toBeVisible();
  const buf = gameCard(page, "NE@BUF");
  await expect(buf).toBeVisible();
  await expect(buf.getByText("CBS")).toBeVisible();
  await expect(buf.getByText("Final")).toBeVisible();
  const allen = buf.getByTestId("player-row").filter({ hasText: "Josh Allen" }).filter({ hasText: "Sunday Funday" });
  await expect(allen).toContainText("My starter");
  await expect(allen).toContainText("19.52");

  // Default filters: starters only, irrelevant games hidden.
  await expect(page.locator('[data-ownership="OPPONENT"][data-testid="player-row"]')).toHaveCount(0);
  await expect(gameCard(page, "ATL@NO")).toHaveCount(0); // only Bijan (bench) plays here -> hidden
  await expect(gameCard(page, "DET@CAR")).toHaveCount(0); // only Amon-Ra (bench) plays here -> hidden

  await expect(page.getByRole("radio", { name: "Most relevant" })).toHaveAttribute("aria-checked", "true");
  await expectNoHorizontalScroll(page);
});

test("game order: most relevant, kickoff time, not finished — persisted across reload", async ({ page }) => {
  await connectYahooAndImport(page);
  await page.getByRole("button", { name: "All NFL games" }).click();
  const order = () =>
    page.getByTestId("game-card").evaluateAll((els) => els.map((e) => e.getAttribute("data-kickoff")!));

  await page.getByRole("radio", { name: "Kickoff time" }).click();
  const kickoffs = await order();
  expect(kickoffs).toEqual([...kickoffs].sort((a, b) => Date.parse(a) - Date.parse(b)));

  await page.getByRole("radio", { name: "Not finished" }).click();
  await expect(gameCard(page, "NE@BUF")).toHaveCount(0); // final
  await expect(gameCard(page, "MIA@MIN")).toBeVisible(); // live

  await page.reload();
  await expect(page.getByRole("radio", { name: "Not finished" })).toHaveAttribute("aria-checked", "true");
  await expect(gameCard(page, "NE@BUF")).toHaveCount(0);
});

test("5–6: bench and opponent toggles, persisted across reload", async ({ page }) => {
  await connectYahooAndImport(page);
  const jefferson = page.getByTestId("player-row").filter({ hasText: "Justin Jefferson" });
  await expect(jefferson).toHaveCount(0);

  await page.getByRole("button", { name: "Bench", exact: true }).click();
  await expect(jefferson).toContainText("My bench");
  await expect(jefferson).toContainText("Q");

  await page.getByRole("button", { name: "Opponents" }).click();
  const buf = gameCard(page, "NE@BUF");
  // Same player, two leagues, two separate contexts.
  const opp = buf.getByTestId("player-row").filter({ hasText: "Josh Allen" }).filter({ hasText: "Work League" });
  await expect(opp).toContainText("Opponent");
  await expect(opp).toContainText("20.52");

  await page.reload();
  await expect(page.getByRole("button", { name: "Bench", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(jefferson).toBeVisible();

  await page.getByRole("button", { name: "All NFL games" }).click();
  await expect(page.getByTestId("game-card")).toHaveCount(16);
  await expectNoHorizontalScroll(page);
});

test("7: matchups list and detail", async ({ page }) => {
  await connectYahooAndImport(page);
  await page.getByRole("link", { name: "Matchups" }).click();
  const card = page.getByTestId("matchup-card").filter({ hasText: "Sunday Funday" });
  await expect(card).toContainText("Ankit's Aces");
  await expect(card).toContainText("112.34");
  await expect(card).toContainText("Gridiron Gurus");
  await expect(card).toContainText("98.76");
  await expect(card).toContainText("Winning by 13.58");
  await expect(page.getByTestId("matchup-card")).toHaveCount(2);

  await card.click();
  await expect(page.getByTestId("lineup-You")).toContainText("Josh Allen");
  await expect(page.getByTestId("lineup-Opponent")).toContainText("Lamar Jackson");
  await expectNoHorizontalScroll(page);
});

test("9: expired Yahoo token shows reconnect banner, reconnect clears it", async ({ page }) => {
  await connectYahooAndImport(page, ["Sunday Funday"]);
  const resp = await page.request.post("/api/providers/yahoo/_fixture/expire");
  expect(resp.ok()).toBeTruthy();

  await page.reload();
  const banner = page.getByTestId("reconnect-banner");
  await expect(banner).toContainText("Your Yahoo connection has expired");
  // Last synced rosters keep rendering.
  await expect(gameCard(page, "NE@BUF").getByText("Josh Allen")).toBeVisible();

  await banner.getByRole("link", { name: "Reconnect Yahoo" }).click();
  await expect(page).toHaveURL(/\/teams\/yahoo\/select$/);
  await page.getByRole("link", { name: "Games" }).click();
  await expect(page.getByRole("heading", { name: "Week 4" })).toBeVisible();
  await expect(page.getByTestId("reconnect-banner")).toHaveCount(0);
});
