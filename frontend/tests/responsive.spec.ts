import { expect, test } from "@playwright/test";

const routes = ["/", "/about", "/login", "/disease", "/yield", "/dashboard"];
const viewports = [
  { width: 360, height: 800 },
  { width: 390, height: 844 },
  { width: 768, height: 900 },
  { width: 1280, height: 900 },
];

for (const route of routes) {
  for (const viewport of viewports) {
    test(`${route} fits ${viewport.width}px without horizontal overflow`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto(`http://127.0.0.1:3000${route}`);
      await page.waitForLoadState("domcontentloaded");

      const dimensions = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));

      expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
      await expect(page.locator("main")).toBeVisible();
    });
  }
}
