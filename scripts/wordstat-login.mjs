// Разовый вход в Яндекс для сборщика Вордстата.
//
// Вордстат без авторизации отдаёт пустую таблицу — сбор молча собирает нули.
// Скрипт открывает окно с тем же профилем, что использует harvest, и ждёт,
// пока в таблице появятся строки: это и есть признак рабочей сессии.
// После этого профиль сохранён, и сбор можно запускать сколько угодно раз.
//
//   node scripts/wordstat-login.mjs

import { chromium } from 'playwright';

const PROFILE = process.env.WM_PROFILE || '.wordstat-profile';
const WAIT_MIN = Number(process.env.LOGIN_WAIT || 10);

const ctx = await chromium.launchPersistentContext(PROFILE, {
  headless: false,
  viewport: { width: 1500, height: 1000 },
  locale: 'ru-RU',
  args: ['--disable-blink-features=AutomationControlled'],
  ignoreDefaultArgs: ['--enable-automation'],
});
const page = ctx.pages()[0] || (await ctx.newPage());
await page.goto('https://wordstat.yandex.ru/?region=225&words=' + encodeURIComponent('метафорические карты'),
                { waitUntil: 'domcontentloaded' }).catch(() => {});

console.log(`Окно открыто. Войдите в Яндекс — жду до ${WAIT_MIN} минут.`);
console.log('Как увижу непустую таблицу Вордстата, закрою окно сам.');

const deadline = Date.now() + WAIT_MIN * 60_000;
let ok = false;
while (Date.now() < deadline) {
  const n = await page.evaluate(() => {
    let c = 0;
    for (const tr of document.querySelectorAll('tr')) {
      const td = tr.querySelectorAll('td');
      if (td.length >= 2 && /\d/.test(td[1].innerText)) c++;
    }
    return c;
  }).catch(() => 0);
  if (n > 5) { ok = true; console.log(`Сессия рабочая: таблица отдаёт ${n} строк.`); break; }
  await new Promise((r) => setTimeout(r, 3000));
}
if (!ok) console.log('Не дождался: таблица так и не наполнилась. Профиль всё равно сохранён.');
await ctx.close();
process.exit(ok ? 0 : 3);
