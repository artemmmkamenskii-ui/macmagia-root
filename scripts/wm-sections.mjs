// Обход разделов Яндекс.Вебмастера по ссылкам из его же навигации.
//
// Адреса разделов в интерфейсе не совпадают с теми, что напрашиваются из
// host_id: /diagnostics/, /search-queries/popular/ и прочие отдают 404.
// Поэтому не угадываем — заходим на сайт, собираем ссылки меню и ходим
// по ним, сохраняя текст, таблицы и снимок каждого раздела.
//
//   WM_PROFILE=… WM_OUT=… node scripts/wm-sections.mjs

import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'fs';

const PROFILE = process.env.WM_PROFILE;
const OUT = process.env.WM_OUT;
mkdirSync(OUT, { recursive: true });

const ctx = await chromium.launchPersistentContext(PROFILE, {
  headless: false,
  viewport: { width: 1500, height: 950 },
  locale: 'ru-RU',
  args: ['--disable-blink-features=AutomationControlled'],
});
const page = ctx.pages()[0] || (await ctx.newPage());
page.setDefaultTimeout(45000);

await page.goto('https://webmaster.yandex.ru/sites/', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(3000);
await page.getByText('macmagia.ru', { exact: false }).first().click({ timeout: 20000 });
await page.waitForURL(/\/site\//, { timeout: 30000 });
await page.waitForTimeout(4000);

// Ссылки меню — единственный надёжный источник адресов разделов.
const links = await page.evaluate(() =>
  [...document.querySelectorAll('a[href*="/site/"]')]
    .map((a) => ({ href: a.href, text: a.innerText.trim().replace(/\s+/g, ' ').slice(0, 40) }))
    .filter((x) => x.text && !/^\d+$/.test(x.text))
);
const seen = new Set();
const uniq = links.filter((l) => !seen.has(l.href) && seen.add(l.href));
console.log('ссылок в навигации:', uniq.length);
writeFileSync(`${OUT}/_menu.json`, JSON.stringify(uniq, null, 1), 'utf-8');

let i = 0;
for (const { href, text } of uniq) {
  i++;
  const name = String(i).padStart(2, '0') + '-' +
    (href.split('/site/')[1] || '').split('/').slice(1).join('-').replace(/[^a-z0-9-]/gi, '') || 'x';
  try {
    await page.goto(href, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4500);
    const body = await page.evaluate(() => document.body.innerText);
    if (body.includes('Ошибка 404')) { console.log(`  ✗ 404  ${text}`); continue; }
    const tables = await page.evaluate(() =>
      [...document.querySelectorAll('table')].map((t) =>
        [...t.querySelectorAll('tr')].map((tr) =>
          [...tr.querySelectorAll('th,td')].map((c) => c.innerText.trim()))));
    writeFileSync(`${OUT}/${name}.txt`, `${text}\n${href}\n\n${body}`, 'utf-8');
    writeFileSync(`${OUT}/${name}.json`, JSON.stringify({ text, href, tables }, null, 1), 'utf-8');
    console.log(`  ✓ ${text}  (${body.length} знаков, таблиц ${tables.length})`);
  } catch (e) {
    console.log(`  ✗ ${text}: ${String(e.message).slice(0, 80)}`);
  }
}
console.log('готово →', OUT);
await ctx.close();
