// Сбор частот из Вордстата браузером под живой сессией Яндекса.
//
// Зачем браузер: у Вордстата есть API, но только через Директ, а наш
// OAuth-токен — со скоупами Метрики и Вебмастера (ошибка 53 «Недействительный
// OAuth-токен»). Интерфейс под сессией отдаёт то же самое.
//
// Сиды берутся из docs/seo/wordstat-seeds/NN-*.md — из блока ``` ``` ```,
// строки с # пропускаются. Результат пишется рядом: NN-slug-wordstat.csv.
//
// Резюмируемый: уже собранные сиды пропускаются, поэтому прерывать и
// перезапускать безопасно. Капчу распознаёт и останавливается — дальше нужен
// человек, автоматически её обходить не пытаемся.
//
// Playwright в этом проекте не установлен — запускать из «Провизора», где он
// есть, указав папку с сидами отсюда:
//
//   cd "../2. Провизор/frontend" && \
//   WS_DIR="../../1. общий лендинг/docs/seo/wordstat-seeds" \
//   WM_PROFILE="../../1. общий лендинг/.wordstat-profile" \
//   node "../../1. общий лендинг/scripts/wordstat-harvest.mjs" [NN …]
//
// Первый запуск: откроется окно браузера — войдите в Яндекс руками, профиль
// сохранится и дальше подхватится сам. Без аргументов проходит все блоки.

import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync, appendFileSync, readdirSync } from 'fs';
import { join } from 'path';

const DIR = process.env.WS_DIR || 'docs/seo/wordstat-seeds';
const PROFILE = process.env.WM_PROFILE || '.wordstat-profile';
const REGION = 225;                 // Россия
// Сколько раз жать «Показать ещё». Страница — 200 фраз, поэтому 6 нажатий
// давали ровно 1400 строк, и это выглядело потолком Вордстата, хотя было моим
// лимитом. Держим с запасом: у исчерпавшихся сидов кнопка исчезает сама.
const MORE_CLICKS = Number(process.env.WS_CLICKS || 30);
const PAUSE = 4000;                 // между действиями, чтобы не ловить капчу
const only = process.argv.slice(2);

function seedsOf(file) {
  const s = readFileSync(join(DIR, file), 'utf-8');
  const m = s.match(/```\n([\s\S]*?)\n```/);
  if (!m) return [];
  return m[1].split('\n').map((x) => x.trim()).filter((x) => x && !x.startsWith('#'));
}

const blocks = readdirSync(DIR)
  .filter((f) => /^\d\d-.*\.md$/.test(f))
  .sort()
  .filter((f) => !only.length || only.includes(f.slice(0, 2)));

const ctx = await chromium.launchPersistentContext(PROFILE, {
  headless: false,
  viewport: { width: 1500, height: 1000 },
  locale: 'ru-RU',
  args: ['--disable-blink-features=AutomationControlled'],
  ignoreDefaultArgs: ['--enable-automation'],
});
const page = ctx.pages()[0] || (await ctx.newPage());
page.setDefaultTimeout(60000);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function captcha() {
  const t = await page.evaluate(() => document.body.innerText).catch(() => '');
  return /подтвердите, что запросы отправляли вы|введите символы|я не робот|captcha/i.test(t);
}

// Таблицу читаем выборкой из DOM, а не скриншотом — вернётся весь список.
async function rows() {
  return page.evaluate(() => {
    const out = [];
    for (const tr of document.querySelectorAll('tr')) {
      const c = [...tr.querySelectorAll('td')].map((x) => x.innerText.trim());
      if (c.length >= 2) {
        const n = parseInt(c[1].replace(/\s/g, ''), 10);
        if (c[0] && Number.isFinite(n)) out.push([c[0], n]);
      }
    }
    return out;
  });
}

async function harvest(seed, tab) {
  const u = `https://wordstat.yandex.ru/?region=${REGION}&words=${encodeURIComponent(seed)}${tab === 'similar' ? '&view=similar' : ''}`;
  await page.goto(u, { waitUntil: 'domcontentloaded' });
  await sleep(PAUSE);
  if (await captcha()) return null;
  if (tab === 'similar') {
    try {
      await page.getByText('Похожие', { exact: true }).first().click({ timeout: 8000 });
      await sleep(PAUSE);
    } catch {}
  }
  for (let i = 0; i < MORE_CLICKS; i++) {
    try {
      const btn = page.getByText('Показать ещё', { exact: false }).first();
      if (!(await btn.isVisible({ timeout: 4000 }).catch(() => false))) break;
      await btn.click();
      await sleep(PAUSE);
      if (await captcha()) return null;
    } catch { break; }
  }
  return rows();
}

for (const file of blocks) {
  const seeds = seedsOf(file);
  const out = join(DIR, file.replace(/\.md$/, '-wordstat.csv'));
  if (!existsSync(out)) writeFileSync(out, 'seed,tab,query,shows\n', 'utf-8');
  // Сид пишется в CSV через JSON.stringify, то есть в кавычках. Сверять с
  // «сырым» значением нельзя — совпадений не будет никогда, и резюме
  // молча перекачает всё заново.
  // Сид, набравший ровно прежний предел, считаем недособранным: его обрезала
  // настройка, а не Вордстат. Число задаётся через WS_REDO.
  const redoAt = Number(process.env.WS_REDO || 0);
  const counts = new Map();
  for (const l of readFileSync(out, 'utf-8').split('\n').slice(1)) {
    const k = l.split(',')[0];
    if (!k) continue;
    let name; try { name = JSON.parse(k); } catch { name = k; }
    counts.set(name, (counts.get(name) || 0) + 1);
  }
  const done = new Set(
    readFileSync(out, 'utf-8').split('\n').slice(1)
      .map((l) => l.split(',')[0])
      .filter(Boolean)
      .map((x) => { try { return JSON.parse(x); } catch { return x; } })
      .filter((name) => !(redoAt && counts.get(name) >= redoAt))
  );
  console.log(`\n##### ${file}: сидов ${seeds.length}, уже собрано ${done.size}`);
  for (const seed of seeds) {
    if (done.has(seed)) { console.log(`  · ${seed} — пропуск`); continue; }
    let total = 0;
    // Вкладка «Похожие» на проверке отдала ровно то же, что «Популярные»
    // (5450 строк против 5450, уникальных 5373 из 10 900) — переключение не
    // срабатывает, а время удваивается. Синонимы и так заданы сидами.
    for (const tab of ['popular']) {
      const r = await harvest(seed, tab);
      if (r === null) {
        console.log('\n!!! КАПЧА. Решите её в окне и перезапустите — собранное сохранено.');
        await ctx.close();
        process.exit(2);
      }
      total += r.length;
      const csv = r.map(([q, n]) => `${JSON.stringify(seed)},${tab},${JSON.stringify(q)},${n}`).join('\n');
      if (csv) appendFileSync(out, csv + '\n', 'utf-8');
      await sleep(PAUSE);
    }
    console.log(`  ✓ ${seed} — ${total} фраз`);
  }
}
console.log('\nготово');
await ctx.close();
