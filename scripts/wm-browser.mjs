// Обход Яндекс.Вебмастера глазами, а не через API.
//
// Зачем: часть отчётов API не отдаёт вовсе — внешние ссылки возвращают 403,
// исключённые страницы 404. Их видно только в интерфейсе с живой сессией.
//
// Профиль браузера лежит отдельно от вашего Chrome (его не трогаем и не
// закрываем). Первый запуск: откроется окно, нужно войти в Яндекс руками —
// скрипт подождёт. Дальше сессия переиспользуется, вход больше не нужен.
//
//   cd frontend && WM_PROFILE=… WM_OUT=… node ./wm-browser.mjs
//
// Адрес разделов не собираем из host_id руками — он в интерфейсе другой,
// чем в API. Берём настоящую ссылку на сайт со страницы со списком сайтов.

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

console.log('→ список сайтов');
await page.goto('https://webmaster.yandex.ru/sites/', { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(4000);

if (page.url().includes('passport')) {
  console.log('\n  ВОЙДИТЕ В ЯНДЕКС В ОКНЕ — жду до 10 минут…\n');
  for (let i = 0; i < 120 && page.url().includes('passport'); i++) await page.waitForTimeout(5000);
}

// Не угадываем host_id: кликаем по карточке сайта и берём адрес из
// строки браузера — иначе в ссылку попадает пункт меню («/site/dashboard»).
let base = null;
try {
  await page.getByText('macmagia.ru', { exact: false }).first().click({ timeout: 20000 });
  await page.waitForURL(/\/site\//, { timeout: 30000 });
  await page.waitForTimeout(3000);
  const u = new URL(page.url());
  const parts = u.pathname.split('/').filter(Boolean); // ['site', '<id>', …]
  if (parts[0] === 'site' && parts[1]) base = `${u.origin}/site/${parts[1]}`;
} catch (e) {
  console.log('  не удалось кликнуть по сайту:', String(e.message).slice(0, 100));
}

console.log('✓ база разделов:', base);

const sections = [
  ['dashboard', '/dashboard/'],
  ['diagnostics', '/diagnostics/'],
  ['links-external', '/links/external/'],
  ['links-internal', '/links/internal/'],
  ['pages-excluded', '/indexing/indexing-history/?filter=excluded'],
  ['pages-in-search', '/indexing/pages-in-search/'],
  ['search-queries', '/search-queries/popular/'],
  ['recommendations', '/recommendations/'],
  ['security', '/security/'],
];

for (const [name, path] of sections) {
  const url = base + path;
  try {
    console.log(`\n=== ${name}  ${url}`);
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(5000);
    const text = await page.evaluate(() => document.body.innerText);
    if (text.includes('Ошибка 404')) {
      console.log('  ✗ 404 — раздел по этому адресу не живёт');
      continue;
    }
    // Таблицы читаем выборкой из DOM, а не скриншотом — вернётся весь список.
    const tables = await page.evaluate(() =>
      [...document.querySelectorAll('table')].map((t) =>
        [...t.querySelectorAll('tr')].map((tr) =>
          [...tr.querySelectorAll('th,td')].map((c) => c.innerText.trim())
        )
      )
    );
    const outside = await page.evaluate(() =>
      [...document.querySelectorAll('a[href^="http"]')]
        .map((a) => ({ href: a.href, text: a.innerText.trim().slice(0, 90) }))
        .filter((x) => !/yandex\.(ru|com|net)/.test(new URL(x.href).hostname))
        .slice(0, 500)
    );
    writeFileSync(`${OUT}/${name}.txt`, text, 'utf-8');
    writeFileSync(`${OUT}/${name}.json`, JSON.stringify({ url, tables, outside }, null, 1), 'utf-8');
    await page.screenshot({ path: `${OUT}/${name}.png` });
    console.log(`  текста ${text.length}, таблиц ${tables.length}, внешних ссылок ${outside.length}`);
  } catch (e) {
    console.log(`  ✗ ${name}: ${String(e.message).slice(0, 120)}`);
  }
}

console.log(`\nготово → ${OUT}`);
await ctx.close();
