import { test, expect } from "@playwright/test";

async function setDay(page, day) {
  const slider = page.getByRole("slider", { name: "Mission day", exact: true });
  await slider.focus();
  await slider.press("Home");
  for (let i = 1; i < day; i++) await slider.press("ArrowRight");
  await expect(slider).toHaveValue(String(day));
}

async function choose(page, id) {
  await expect(page.getByRole("heading", { name: /Mission overview/ })).toBeVisible();
  const toggle = page.getByRole("button", { name: /^Astronaut / });
  if (await toggle.isVisible()) await toggle.click();
  await page.getByRole("searchbox", { name: "Search astronaut profiles" }).fill(id);
  await page.getByRole("button", { name: `Select astronaut ${id}`, exact: true }).click();
}

test("fixed published scans, measurements and selected record agree", async ({ page, request }, testInfo) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/#dashboard");
  await expect(page.getByRole("heading", { name: /Mission overview/ })).toBeVisible();
  await setDay(page, 15);
  await page.getByRole("tab", { name: "Measurements", exact: true }).click();
  await expect(page.getByText(/fixed_7_day_day1_anchor/)).toBeVisible();
  await expect(page.getByText(/Personal ONSD baseline/)).toBeVisible();
  const rows = (await (await request.get("/data/pipeline/crew_observations.jsonl")).text()).trim().split(/\r?\n/).map(JSON.parse);
  const row = rows.find(r => r.astronaut_id === "A1" && r.day === 15);
  await expect(page.getByText(`${row.scan.onsd_mm.toFixed(2)}`, { exact: false }).first()).toBeVisible();
  await page.getByRole("button", { name: "Timeline", exact: true }).click();
  await page.getByRole("tab", { name: "Records", exact: true }).click();
  const selected = page.locator('tr[aria-current="true"]');
  await expect(selected).toContainText("15");
  await expect(selected).toContainText(`${row.scan.onsd_mm.toFixed(2)} mm`);
  await expect(page.getByText(/Selected day 15 is revealed automatically/)).toBeVisible();
  await page.screenshot({ path: `test-results/records-${testInfo.project.name}.png`, fullPage: true });
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
});

test("gated dual-measurement cases expose justified Consult and complete delayed consultation", async ({ page }, testInfo) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/#engineering-dashboard");
  await expect(page.getByText(/ENGINEERING FIXTURE · User-relayed model/)).toBeVisible();
  await choose(page, "E4");
  await setDay(page, 15);
  await expect(page.locator(".pv-tile-tier").filter({ hasText: "Consult" }).first()).toBeVisible();
  await page.getByRole("tab", { name: "Measurements", exact: true }).click();
  await expect(page.getByText(/mm²/).first()).toBeVisible();
  await page.getByRole("button", { name: "Timeline", exact: true }).click();
  await page.getByRole("tab", { name: "Jugular trace", exact: true }).click();
  await expect(page.getByRole("img", { name: "Jugular area by mission day" })).toBeVisible();
  await page.screenshot({ path: `test-results/jugular-${testInfo.project.name}.png`, fullPage: true });
  await page.getByRole("button", { name: "Earth link", exact: true }).click();
  await page.getByRole("tab", { name: "Consultation", exact: true }).click();
  const delay = page.getByRole("slider", { name: "Consultation one-way delay" });
  await delay.focus();
  await delay.press("Home");
  await delay.press("ArrowRight");
  await page.getByRole("button", { name: "Suggest SANS review" }).click();
  for (const name of ["Request consultation", "Queue request", "Transmit to Earth"]) await page.getByRole("button", { name, exact: true }).click();
  await expect(page.getByText("Request and evidence have not reached Earth.")).toBeVisible();
  const receive = page.getByRole("button", { name: "Receive on Earth", exact: true });
  await expect(receive).toBeEnabled({ timeout: 5000 });
  await receive.click();
  for (const name of ["Open ground review", "Prepare simulated response", "Send response to crew"]) await page.getByRole("button", { name, exact: true }).click();
  const response = page.getByRole("button", { name: "Receive crew response", exact: true });
  await expect(response).toBeEnabled({ timeout: 5000 });
  await response.click();
  await page.getByRole("button", { name: "Acknowledge and close", exact: true }).click();
  await expect(page.getByText("Case acknowledged and closed", { exact: true })).toBeVisible();
  await page.getByText("Consultation audit trail (10 states)").click();
  await expect(page.locator(".pv-consult-case li")).toHaveCount(10);
  await page.screenshot({ path: `test-results/consultation-${testInfo.project.name}.png`, fullPage: true });
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
});

test("research reports the exact gate and Urgent fixture follows daily scan protocol", async ({ page }) => {
  await page.goto("/#engineering-dashboard");
  await choose(page, "E5");
  await setDay(page, 2);
  await expect(page.locator(".pv-tile-tier").filter({ hasText: "Urgent" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Research", exact: true }).click();
  await expect(page.getByText("Scientific comparison blocked", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Blockers", exact: true }).click();
  await page.getByRole("button", { name: /Research v1 written confirmation/i }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText(/independent|Confirm specification/);
});
