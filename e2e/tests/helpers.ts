import { expect, type Page } from "@playwright/test";

/** Flows 1–3: first-time add team -> connect Yahoo (fake OAuth) -> import -> confirm team. */
export async function connectYahooAndImport(page: Page, leagues = ["Sunday Funday", "Work League"]) {
  await page.goto("/");
  await expect(page.getByTestId("empty-state")).toBeVisible();
  await page.getByRole("link", { name: "Add Fantasy Team" }).click();
  await expect(page).toHaveURL(/\/teams\/new$/);
  await page.getByRole("link", { name: /Yahoo Fantasy/ }).click();

  await expect(page).toHaveURL(/\/teams\/yahoo\/select$/);
  for (const name of leagues) await page.getByRole("checkbox", { name: new RegExp(name) }).click();
  await page.getByRole("button", { name: /^Import/ }).click();

  await expect(page.getByRole("heading", { name: "Confirm your teams" })).toBeVisible();
  // Yahoo's owned team is pre-selected in every league.
  for (const name of leagues) {
    const group = page.getByRole("radiogroup", { name: `Your team in ${name}` });
    await expect(group.getByRole("radio", { checked: true })).toHaveCount(1);
  }
  await page.getByRole("button", { name: "Confirm and go to Games" }).click();
  await expect(page).toHaveURL(/\/$/);
}

export function gameCard(page: Page, matchup: string) {
  return page.locator(`[data-testid="game-card"][data-game="${matchup}"]`);
}

export async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}
