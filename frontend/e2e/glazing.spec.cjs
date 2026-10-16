const { test, expect } = require('@playwright/test');
const { PNG } = require('pngjs');

test('glazing draft renders native colours and remains interactive', async ({ page }, info) => {
  const job = process.env.GLAZING_JOB;
  test.skip(!job, 'Set GLAZING_JOB to the glazing comparison draft');
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`/designs/${job}`);
  const reset = page.getByRole('button', { name: '恢复视角', exact: true });
  await expect(reset).toBeVisible({ timeout: 60000 });
  const canvas = page.locator('.assembly-canvas canvas');
  await canvas.scrollIntoViewIfNeeded();
  const first = await canvas.screenshot({ path: info.outputPath('glazing.png') });
  const pixels = PNG.sync.read(first);
  const colours = new Set();
  let green = 0;
  for (let i = 0; i < pixels.data.length; i += 4) {
    const [r, g, b] = pixels.data.subarray(i, i + 3);
    colours.add(pixels.data.readUInt32BE(i));
    if (g > r * 1.15 && g > b * 1.15) green++;
  }
  expect(colours.size).toBeGreaterThan(100);
  expect(green).toBeGreaterThan(500);
  const box = await canvas.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 140, box.y + box.height / 2 + 45, { steps: 12 });
  await page.mouse.up();
  await expect.poll(async () => first.equals(await canvas.screenshot())).toBe(false);
  await canvas.screenshot({ path: info.outputPath('glazing-rotated.png') });
  await reset.click();
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
