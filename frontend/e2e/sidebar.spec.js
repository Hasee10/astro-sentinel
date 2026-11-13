import { test, expect } from "@playwright/test";

for (const [width, height] of [[1280, 720], [1440, 900], [1024, 600]]) {
  test(`sidebar pager and research footer never overlap at ${width}x${height}`, async ({ page }, info) => {
    test.skip(info.project.name !== "desktop", "Desktop size regression");
    await page.setViewportSize({ width, height });
    await page.goto("/#dashboard");
    const sidebar = page.getByRole("complementary", { name: "Synthetic cohort browser" });
    const pager = sidebar.getByRole("navigation", { name: "Cohort pages" });
    const next = pager.getByRole("button", { name: "Next cohort pages" });
    await expect(next).toBeEnabled();
    const first = await sidebar.locator(".pv-profile-name").first().innerText();
    await next.click();
    await expect(sidebar.locator(".pv-profile-name").first()).not.toHaveText(first);
    const research = sidebar.getByRole("button", { name: "Research details" });
    await research.scrollIntoViewIfNeeded();
    const boxes = await sidebar.evaluate(element => {
      const list = element.querySelector(".pv-crew-list").getBoundingClientRect();
      const pager = element.querySelector(".pv-pager").getBoundingClientRect();
      const footer = element.querySelector(".pv-sidebar-bottom").getBoundingClientRect();
      return { listBottom: list.bottom, pagerTop: pager.top, pagerBottom: pager.bottom, footerTop: footer.top };
    });
    expect(boxes.listBottom).toBeLessThanOrEqual(boxes.pagerTop + 1);
    expect(boxes.pagerBottom).toBeLessThanOrEqual(boxes.footerTop);
    await sidebar.screenshot({ path: `test-results/sidebar-${width}-${height}.png` });
    await research.click();
    await expect(page.getByRole("heading", { name: "Research & readiness" })).toBeVisible();
  });
}

test("mobile profile picker keeps pagination reachable in a short viewport", async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "Explicit mobile viewport regression");
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto("/#dashboard");
  await page.getByRole("button", { name: /^Astronaut / }).click();
  const next = page.getByRole("button", { name: "Next cohort pages" });
  await expect(next).toBeEnabled();
  await next.click();
  const box = await next.boundingBox();
  expect(box.y + box.height).toBeLessThanOrEqual(667);
  expect(await page.locator(".pv-profile").count()).toBeGreaterThan(0);
});
