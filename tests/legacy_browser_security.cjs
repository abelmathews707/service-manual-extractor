const {chromium} = require('playwright');

(async () => {
  const target = process.argv[2];
  const origin = new URL(target).origin;
  const browser = await chromium.launch({
    executablePath: process.env.REPAIR_BUDDY_TEST_CHROME,
    headless: true,
    timeout: 15000,
  });
  try {
    const context = await browser.newContext();
    const outsideRequests = [];
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin !== origin) {
        outsideRequests.push(route.request().url());
        return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    await page.goto(target);
    await page.waitForFunction(() => document.documentElement.dataset.security,
      null, {timeout: 10000});
    const result = await page.getAttribute('html', 'data-security');
    if (result !== 'passed' || outsideRequests.length) {
      throw new Error(JSON.stringify({result, outsideRequests}));
    }
    console.log('security passed');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
