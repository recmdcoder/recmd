// Renders each *.html file in this directory to a PNG sized for the
// 6.5" iPhone App Store screenshot spec (1242 x 2688).
const path = require('path');
const fs = require('fs');
const { chromium } = require('/opt/node22/lib/node_modules/playwright');

const dir = __dirname;
const files = fs.readdirSync(dir).filter(f => /^\d.*\.html$/.test(f)).sort();

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1242, height: 2688 },
    deviceScaleFactor: 1,
  });
  const page = await ctx.newPage();

  for (const f of files) {
    const url = 'file://' + path.join(dir, f);
    const out = path.join(dir, f.replace(/\.html$/, '.png'));
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.screenshot({ path: out, fullPage: false, omitBackground: false });
    console.log('Wrote', out);
  }

  await browser.close();
})().catch(err => { console.error(err); process.exit(1); });
