// Список страниц с одинаковыми description лежит за вкладкой, а не в тексте раздела.
import { chromium } from 'playwright';
const ctx = await chromium.launchPersistentContext('/tmp/wm-copy', {
  channel: 'chrome', headless: false, viewport: { width: 1500, height: 950 }, locale: 'ru-RU',
});
const page = ctx.pages()[0] || (await ctx.newPage());
page.setDefaultTimeout(45000);
await page.goto('https://webmaster.yandex.ru/site/https:macmagia.ru:443/indexing/double-descriptions/', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(6000);
try { await page.getByRole('tab', { name: /description/i }).click({ timeout: 8000 }); } catch {}
await page.waitForTimeout(5000);
const rows = await page.evaluate(() =>
  [...document.querySelectorAll('table tr')].map(tr =>
    [...tr.querySelectorAll('th,td')].map(c => c.innerText.trim()).filter(Boolean).join(' | ')
  ).filter(Boolean)
);
console.log(rows.slice(0, 40).join('\n'));
const links = await page.evaluate(() =>
  [...document.querySelectorAll('a[href*="macmagia"], a[href^="/blog"], a[href^="https://macmagia"]')]
    .map(a => a.getAttribute('href')).filter(h => h && !h.includes('webmaster')).slice(0, 40));
console.log('\nссылки:', [...new Set(links)].join('\n'));
await ctx.close();
