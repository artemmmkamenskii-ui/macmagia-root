// Метрика через браузер: API требует OAuth-токена, а живая сессия у нас уже
// есть — та же, что для Вебмастера.
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'fs';
const OUT = process.env.MT_OUT || '/tmp/metrika';
mkdirSync(OUT, { recursive: true });
const ID = process.env.MT_ID || '109562142';
const ctx = await chromium.launchPersistentContext(process.env.WM_PROFILE, {
  channel: 'chrome', headless: false, viewport: { width: 1600, height: 1000 }, locale: 'ru-RU' });
const page = ctx.pages()[0] || (await ctx.newPage());
page.setDefaultTimeout(45000);

const pages = [
  ['svodka', `https://metrika.yandex.ru/dashboard?id=${ID}&period=week`],
  ['stranicy', `https://metrika.yandex.ru/stat/popular?id=${ID}&period=week`],
  ['istochniki', `https://metrika.yandex.ru/stat/sources_summary?id=${ID}&period=week`],
];
for (const [name, url] of pages) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(16000);   // отчёты грузятся долго, таблица приходит позже текста
    const txt = await page.evaluate(() => document.body.innerText);
    const rows = await page.evaluate(() =>
      [...document.querySelectorAll('[class*="table"] tr, table tr')].slice(0, 25)
        .map(tr => [...tr.querySelectorAll('td,th')].map(c => c.innerText.replace(/\n+/g, ' ').trim()).filter(Boolean).join(' | '))
        .filter(Boolean));
    if (rows.length) writeFileSync(`${OUT}/${name}-table.txt`, rows.join('\n'), 'utf-8');
    if (/passport|Войти/i.test(txt.slice(0, 300))) { console.log('нужен вход в Яндекс'); break; }
    writeFileSync(`${OUT}/${name}.txt`, txt, 'utf-8');
    await page.screenshot({ path: `${OUT}/${name}.png` });
    console.log(`✓ ${name}: ${txt.length} знаков`);
  } catch (e) { console.log(`✗ ${name}: ${String(e.message).slice(0, 70)}`); }
}
await ctx.close();
