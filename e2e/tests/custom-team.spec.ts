import { expect, test } from "@playwright/test";

import { expectNoHorizontalScroll, gameCard } from "./helpers";

test("1 + 8: first-time user builds a custom team and sees it on game day", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("empty-state")).toContainText(
    "Connect your fantasy teams and see every NFL game that matters to you in one place.",
  );
  await page.getByRole("link", { name: "Add Fantasy Team" }).click();
  // Coming-soon providers point to custom teams.
  await expect(page.getByText("Sleeper")).toBeVisible();
  await expect(page.getByText("Coming soon — use a Custom Team for now.").first()).toBeVisible();
  await page.getByRole("link", { name: /Custom team/ }).click();

  await page.getByLabel("Team name").fill("Couch Coaches");
  await page.getByRole("radio", { name: "Half PPR" }).click();
  const search = page.getByLabel("Search NFL players");
  await search.fill("jamarr");
  await page.getByRole("button", { name: "Add Ja'Marr Chase as starter" }).click();
  await search.fill("josh allen");
  await page.getByRole("button", { name: "Add Josh Allen as starter" }).click();
  await search.fill("jefferson");
  await page.getByRole("button", { name: "Add Justin Jefferson to bench" }).click();
  await expect(page.getByRole("region", { name: "Starters" })).toContainText("Ja'Marr Chase");
  await expect(page.getByRole("region", { name: "Bench" })).toContainText("Justin Jefferson");
  await expectNoHorizontalScroll(page);
  await page.getByRole("button", { name: "Save team" }).click();

  await expect(page).toHaveURL(/\/teams$/);
  const card = page.getByTestId("manual-team-card");
  await expect(card).toContainText("Couch Coaches");
  await expect(card).toContainText("Half PPR · 2 starters · 1 bench");

  await page.getByRole("link", { name: "Games" }).click();
  const cin = gameCard(page, "JAX@CIN");
  await expect(cin.getByTestId("player-row").filter({ hasText: "Ja'Marr Chase" })).toContainText("Couch Coaches");
  await expect(gameCard(page, "NE@BUF")).toContainText("Josh Allen");

  // Persists across a fresh page load (server-side anonymous session cookie).
  await page.reload();
  await expect(gameCard(page, "JAX@CIN")).toContainText("Ja'Marr Chase");

  // Matchups-compatible surface: custom team shows with no matchup data.
  await page.getByRole("link", { name: "Matchups" }).click();
  await expect(page.getByTestId("matchup-card")).toContainText("No matchup data");
});

test("custom team edit and delete", async ({ page }) => {
  await page.goto("/teams/custom/new");
  await page.getByLabel("Team name").fill("Temp");
  await page.getByLabel("Search NFL players").fill("josh allen");
  await page.getByRole("button", { name: "Add Josh Allen as starter" }).click();
  await page.getByRole("button", { name: "Save team" }).click();
  await expect(page.getByTestId("manual-team-card")).toContainText("1 starters");

  await page.getByRole("link", { name: "Edit" }).click();
  await page.getByRole("button", { name: "Move Josh Allen to bench" }).click();
  await page.getByLabel("Team name").fill("Temp 2");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByTestId("manual-team-card")).toContainText("Temp 2");
  await expect(page.getByTestId("manual-team-card")).toContainText("0 starters · 1 bench");

  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByTestId("manual-team-card")).toHaveCount(0);
  await expect(page.getByText("No custom teams yet.")).toBeVisible();
});
