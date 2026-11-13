import { test, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const screenshots = fileURLToPath(new URL("../../handoff/frontend/ux-recovery/screenshots/", import.meta.url));
mkdirSync(screenshots, { recursive: true });
async function snap(page, name) { await page.screenshot({ path: join(screenshots, `${name}.png`), fullPage: true }); }
async function nav(page, name) {
  const target = page.getByRole("navigation", { name: "Workspace views" }).getByRole("button", { name, exact: true });
  if (!(await target.isVisible())) await page.getByRole("button", { name: "Workspace navigation", exact: true }).click();
  await target.click();
}
async function day(page, value) {
  const slider = page.getByRole("slider", { name: "Mission day", exact: true });
  await slider.press("Home");
  for (let i = 1; i < value; i++) await slider.press("ArrowRight");
  await expect(slider).toHaveValue(String(value));
}
async function noOverflow(page) {
  expect(await page.evaluate(() => ({ width: window.innerWidth, content: document.documentElement.scrollWidth }))).toEqual(expect.objectContaining({ width: expect.any(Number) }));
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
}

test.describe("responsive visual acceptance", () => {
  for (const width of [375, 390, 768, 1280, 1440]) {
    test(`readable dual cards and sparse plots at ${width}px`, async ({ page, request }) => {
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.setViewportSize({ width, height: 1000 });
      await page.goto("/#engineering-dashboard?profile=E4&day=14");
      await expect(page.getByRole("heading", { name: "Mission overview / E4" })).toBeVisible();
      await expect(page.getByRole("article", { name: "SANS assessment" })).toBeVisible();
      await expect(page.getByRole("article", { name: "Venous assessment" })).toBeVisible();
      const raw = (await (await request.get("/data/fixtures/recovery/crew_observations.jsonl")).text()).trim().split(/\r?\n/).map(JSON.parse);
      const scan = raw.find(row => row.astronaut_id === "E4" && row.day === 14).scan_session.measurements;
      await expect(page.getByRole("article", { name: "SANS assessment" })).toContainText(`${scan.find(m => m.type === "onsd").onsd_mm.toFixed(2)} mm`);
      await expect(page.getByRole("article", { name: "Venous assessment" })).toContainText(`${scan.find(m => m.type === "jugular").jugular_area_mm2.toFixed(1)} mm²`);
      const fonts = await page.locator(".pv-card-section p, .pv-evidence-grid dd, .pv-heading p").evaluateAll(elements => elements.map(el => parseFloat(getComputedStyle(el).fontSize)));
      expect(fonts.every(size => size >= 15)).toBeTruthy();
      if (width <= 760) {
        const sansBox = await page.getByRole("article", { name: "SANS assessment" }).boundingBox();
        const venousBox = await page.getByRole("article", { name: "Venous assessment" }).boundingBox();
        expect(sansBox.width).toBeGreaterThan(width * 0.75);
        expect(venousBox.y).toBeGreaterThanOrEqual(sansBox.y + sansBox.height);
      }
      await noOverflow(page);
      await snap(page, `cards-${width}`);
      await page.getByRole("article", { name: "SANS assessment" }).getByRole("button", { name: "View evidence", exact: true }).click();
      const box = await page.getByRole("dialog").boundingBox();
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(width + 1);
      await page.getByRole("button", { name: "Close dialog" }).click();
      await nav(page, "Timeline");
      await expect(page.getByRole("img", { name: "Optic nerve sheath diameter by mission day" })).toBeVisible();
      expect(await page.locator(".pv-guide-gap").count()).toBeGreaterThan(0);
      const pointDays = await page.locator(".pv-observation-dot").evaluateAll(elements => elements.map(el => Number(el.getAttribute("data-day"))));
      expect(pointDays.every(d => d <= 14)).toBeTruthy();
      if (width === 1440) {
        await page.locator('.pv-observation-dot[data-day="14"]').hover();
        await expect(page.locator(".pv-chart-tip")).toContainText(`${scan.find(m => m.type === "onsd").onsd_mm.toFixed(2)} mm`);
      }
      await noOverflow(page);
      await snap(page, `onsd-${width}`);
      await page.getByRole("tab", { name: "Observed points", exact: true }).click();
      await expect(page.locator(".pv-guide-gap")).toHaveCount(0);
      await page.getByRole("tab", { name: "Jugular trace", exact: true }).click();
      await page.getByRole("tab", { name: "Connected trend", exact: true }).click();
      await expect(page.getByRole("img", { name: "Jugular area by mission day" })).toBeVisible();
      await snap(page, `jugular-${width}`);
      await page.getByRole("tab", { name: "Records", exact: true }).click();
      await expect(page.locator('tr[aria-current="true"]')).toContainText(scan.find(m => m.type === "jugular").jugular_area_mm2.toFixed(1));
      await noOverflow(page);
      if (width === 1440) {
        await snap(page, "records-1440");
        await page.getByRole("tab", { name: "Changes", exact: true }).click();
        await snap(page, "timeline-1440");
        await page.getByRole("tab", { name: "Schedule", exact: true }).click();
        await expect(page.getByRole("heading", { name: "Scan decisions" })).toBeVisible();
        await snap(page, "schedule-1440");
      }
      expect(errors).toEqual([]);
    });
  }
  test("landing preview, current example navigation, results and truthful blocked states", async ({ page }) => {
    await page.goto("/");
    const preview = page.getByLabel("Current engineering data preview");
    await expect(preview).toHaveAttribute("data-profile", "E4");
    await expect(preview).toHaveAttribute("data-day", "14");
    await expect(preview).toContainText("Illustrative engineering simulation — not clinically validated.");
    await expect(preview).toContainText("58.7 mm²");
    await preview.scrollIntoViewIfNeeded();
    await preview.screenshot({ path: join(screenshots, "landing-preview-1440.png") });
    await preview.getByRole("button", { name: "Explore this exact example" }).click();
    await expect(page.getByRole("heading", { name: "Mission overview / E4" })).toBeVisible();
    await expect(page.getByRole("slider", { name: "Mission day", exact: true })).toHaveValue("14");
    await nav(page, "Research");
    await page.getByRole("tab", { name: "Results", exact: true }).click();
    await expect(page.getByRole("heading", { name: "No validated experiment results available" })).toBeVisible();
    await snap(page, "results-blocked-1440");
    await page.getByRole("tab", { name: "Engineering Comparison", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Engineering Comparison", exact: true })).toBeVisible();
    await expect(page.getByText(/Adaptive used 511 more sessions/)).toBeVisible();
    await snap(page, "engineering-comparison-1440");
    await page.getByLabel("Trigger-window usefulness").selectOption("0.9");
    await expect(page.getByLabel("Trigger-window usefulness")).toHaveValue("0.9");
    await page.goto("/#dashboard");
    await expect(page.getByText(/Research cohort · 300 synthetic profiles/)).toBeVisible();
    await expect(page.getByRole("article", { name: "SANS assessment" })).toContainText("Unavailable");
    await snap(page, "research-cohort-1440");
  });
  test("failed-only history has no fabricated Y-value and future measurements stay hidden", async ({ page }) => {
    await page.goto("/#dashboard");
    await expect(page.getByRole("heading", { name: /Mission overview/ })).toBeVisible();
    await day(page, 8);
    await nav(page, "Timeline");
    await expect(page.getByRole("button", { name: "Open failed ONSD record, day 8" })).toBeVisible();
    const days = await page.locator(".pv-observation-dot").evaluateAll(elements => elements.map(el => Number(el.getAttribute("data-day"))));
    expect(days).not.toContain(8);
    expect(days.every(d => d <= 8)).toBeTruthy();
    await page.getByRole("button", { name: "Open failed ONSD record, day 8" }).click();
    await expect(page.getByRole("tab", { name: "Records", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.locator('tr[aria-current="true"]')).toContainText("No value");
  });
  test("200 percent zoom equivalent reflow remains keyboard accessible", async ({ browser }) => {
    // At 200% browser zoom a 1440x1000 physical viewport exposes 720x500 CSS
    // pixels. Use that viewport/DPR pair for deterministic zoom-layout coverage.
    const context = await browser.newContext({ viewport: { width: 720, height: 500 }, deviceScaleFactor: 2 });
    const page = await context.newPage();
    await page.goto("http://127.0.0.1:5173/#engineering-dashboard?profile=E4&day=14");
    await expect(page.getByRole("article", { name: "Venous assessment" })).toBeVisible();
    await noOverflow(page);
    await page.getByRole("button", { name: "Quick tour" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await snap(page, "zoom-200-equivalent");
    await context.close();
  });
  test("landing, mission gateway and operational secondary views stay readable on narrow displays", async ({ page }) => {
    for (const width of [375, 390, 768]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await expect(page.getByRole("heading", { name: /The next frontier/ })).toBeVisible();
      await noOverflow(page);
      const preview = page.getByLabel("Current engineering data preview");
      await expect(preview).toBeVisible();
      await preview.scrollIntoViewIfNeeded();
      await noOverflow(page);
      if (width === 375) await snap(page, "landing-mobile-375");
      await page.goto("/#mission");
      await expect(page.locator(".as-portal-grid")).toBeVisible();
      await noOverflow(page);
      expect(await page.locator(".as-route-card p").evaluateAll(elements => elements.every(el => parseFloat(getComputedStyle(el).fontSize) >= 15))).toBeTruthy();
      expect(await page.locator(".as-route-card").evaluateAll(elements => elements.every(el => {
        const card = el.getBoundingClientRect(), action = el.querySelector("strong").getBoundingClientRect();
        return action.bottom <= card.bottom && action.top >= card.top;
      }))).toBeTruthy();
      if (width === 768) await snap(page, "gateway-768");
    }
    await page.goto("/#engineering-dashboard?profile=E4&day=14");
    await expect(page.getByRole("heading", { name: "Mission overview / E4" })).toBeVisible();
    await page.getByRole("tab", { name: "Measurements", exact: true }).click();
    await expect(page.getByText("Latest recorded jugular area and flow")).toBeVisible();
    await noOverflow(page);
    await nav(page, "Earth link");
    await page.getByRole("tab", { name: "Consultation", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Synthetic medical consultation" })).toBeVisible();
    await noOverflow(page);
    await nav(page, "Research");
    await page.getByRole("tab", { name: "Engineering Comparison", exact: true }).click();
    await expect(page.getByText(/Adaptive used 511 more sessions/)).toBeVisible();
    await noOverflow(page);
    await snap(page, "comparison-tablet-768");
  });
  test("missing required data stays an error instead of presenting a fabricated estimate", async ({ page }) => {
    await page.route("**/data/fixtures/recovery/crew_scored.jsonl", route => route.fulfill({ status: 503, body: "Unavailable" }));
    await page.goto("/#engineering-dashboard");
    await expect(page.getByRole("heading", { name: "Mission data unavailable" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
    await expect(page.getByRole("article", { name: "SANS assessment" })).toHaveCount(0);
  });
  test("card actions, profile changes and mission-day rewind preserve one consistent evidence story", async ({ page, request }) => {
    await page.goto("/#engineering-dashboard?profile=E4&day=14");
    const sans = page.getByRole("article", { name: "SANS assessment" });
    await expect(sans).toContainText("6.12 mm");
    await sans.getByRole("button", { name: "View scan schedule" }).click();
    await expect(page.getByRole("heading", { name: "Scan decisions" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Day 15", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Day 14", exact: true }).click();
    await expect(page.locator('tr[aria-current="true"]')).toContainText("6.12 mm");
    await nav(page, "Overview");
    await sans.getByRole("button", { name: "Consultation workspace", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Synthetic medical consultation" })).toBeVisible();
    await nav(page, "Overview");
    const selector = page.getByRole("button", { name: /^Astronaut / });
    if (await selector.isVisible()) await selector.click();
    await page.getByRole("searchbox", { name: "Search astronaut profiles" }).fill("E1");
    await page.getByRole("button", { name: "Select astronaut E1", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Mission overview / E1" })).toBeVisible();
    await expect(page.getByRole("slider", { name: "Mission day", exact: true })).toHaveValue("1");
    await day(page, 30);
    await day(page, 1);
    const raw = (await (await request.get("/data/fixtures/recovery/crew_observations.jsonl")).text()).trim().split(/\r?\n/).map(JSON.parse);
    const first = raw.find(row => row.astronaut_id === "E1" && row.day === 1).scan_session.measurements.find(m => m.type === "onsd");
    await expect(sans).toContainText(`${first.onsd_mm.toFixed(2)} mm`);
    await expect(sans).not.toContainText("Day 14");
  });
});
