// Позиция сайта в живой выдаче: панель отдаёт усреднённую позицию, а надо
// понять, что видит человек прямо сейчас.
import { chromium } from 'playwright';
const q = process.argv[2] || 'метафорические карты онлайн';
const ctx = await chromium.launchPersistentContext(process.env.WM_PROFILE, {
  channel: 'chrome', headless: false, viewport: { width: 1500, height: 1000 }, locale: 'ru-RU' });
const page = ctx.pages()[0] || (await ctx.newPage());
page.setDefaultTimeout(35000);
const pageNo = Number(process.argv[3] || 0);   // 0 = первая страница
await page.goto('https://ya.ru/search/?text=' + encodeURIComponent(q) + '&p=' + pageNo, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(7000);
const body = await page.evaluate(() => document.body.innerText.slice(0, 400));
if (/капч|robot|не робот/i.test(body)) { console.log('КАПЧА, выдачу не снять'); await ctx.close(); process.exit(0); }
const items = await page.evaluate(() => {
  const out = [];
  document.querySelectorAll('li.serp-item, .serp-item').forEach((el) => {
    const a = el.querySelector('a[href^="http"]');
    if (!a) return;
    try { out.push({ host: new URL(a.href).hostname.replace('www.', ''), title: (el.querySelector('h2, .OrganicTitle')?.innerText || '').slice(0, 70) }); } catch {}
  });
  return out.slice(0, 15);
});
console.log('запрос:', q);
items.forEach((x, i) => console.log(`${String(i + 1 + Number(process.argv[3] || 0) * 10).padStart(2)}. ${x.host}${x.host.includes('macmagia') ? '   ← МЫ' : ''}  ${x.title}`));
await ctx.close();
