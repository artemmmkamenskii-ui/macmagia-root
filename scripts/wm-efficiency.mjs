// Сводка «Эффективность» с выбором периода: Вебмастер по умолчанию отдаёт
// один диапазон, а для динамики нужно сравнить неделю с предыдущей.
import { chromium } from 'playwright';
const ctx = await chromium.launchPersistentContext(process.env.WM_PROFILE, {
  channel: 'chrome', headless: false, viewport: { width: 1500, height: 950 }, locale: 'ru-RU' });
const page = ctx.pages()[0] || (await ctx.newPage());
page.setDefaultTimeout(40000);
await page.goto('https://webmaster.yandex.ru/site/https:macmagia.ru:443/efficiency/statistics/', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(8000);
// Сначала переключаем период: без этого отдаётся диапазон по умолчанию
// и понять, за что цифры, невозможно.
for (const label of [/3 месяца/i, /месяц/i, /неделя/i]) {
  try { await page.getByText(label).first().click({ timeout: 4000 }); await page.waitForTimeout(4000); break; } catch {}
}
const txt = await page.evaluate(() => document.body.innerText);
const i = txt.indexOf('Все запросы');
console.log('--- сводка ---');
console.log(txt.slice(i, i + 300).replace(/\n{2,}/g, '\n'));
const per = txt.match(/[^\n]*(?:недел|месяц|дн[ея]|период|\d{2}\.\d{2}\.\d{4})[^\n]*/gi) || [];
console.log('--- период на экране ---');
console.log([...new Set(per)].slice(0, 6).join('\n'));
await ctx.close();
