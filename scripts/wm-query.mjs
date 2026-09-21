// Один запрос в разрезе дней: показы, клики, позиция. Нужно, когда клики
// просели, а показы те же — так видно, позиция это или сниппет.
import { chromium } from 'playwright';
const ctx = await chromium.launchPersistentContext(process.env.WM_PROFILE, {
  channel: 'chrome', headless: false, viewport: { width: 1600, height: 1000 }, locale: 'ru-RU' });
const page = ctx.pages()[0] || (await ctx.newPage());
page.setDefaultTimeout(40000);
await page.goto('https://webmaster.yandex.ru/site/https:macmagia.ru:443/efficiency/statistics/?specialGroup=TOP_3000_QUERIES&orderBy=total-shows-count&orderDirection=desc',
  { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(9000);
// включаем показатель «Средняя позиция» — по умолчанию он выключен
for (const l of [/Ср\.позиция/i, /средняя позиция/i]) {
  try { await page.getByText(l).first().click({ timeout: 4000 }); await page.waitForTimeout(4000); break; } catch {}
}
const rows = await page.evaluate(() =>
  [...document.querySelectorAll('table tr')].slice(0, 12)
    .map(tr => [...tr.querySelectorAll('th,td')].map(c => c.innerText.replace(/\n+/g, ' ').trim()).filter(Boolean).join(' | '))
    .filter(Boolean));
console.log(rows.join('\n'));
await ctx.close();
