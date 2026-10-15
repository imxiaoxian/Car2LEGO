const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './e2e',
  outputDir: '../runs/desktop-playwright',
  timeout: 60000,
  workers: 1,
  use: {
    baseURL: process.env.DESKTOP_URL || 'http://127.0.0.1:8768',
    launchOptions: { executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe' },
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop-1440', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'desktop-1920', use: { viewport: { width: 1920, height: 1080 } } },
  ],
});
