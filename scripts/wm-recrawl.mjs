// Отправка страниц на переобход в Яндекс.Вебмастере через интерфейс.
//
// У Вебмастера суточная квота на принудительный переобход, и она почти
// всегда простаивает. После правок и после сбоев публикации слать сразу:
// иначе робот придёт сам через недели.
//
// Список адресов — в файле, по одному на строку.
//
//   WM_PROFILE=… WM_URLS=… node scripts/wm-recrawl.mjs

import { chromium } from 'playwright';
import { readFileSync } from 'fs';

const PROFILE = process.env.WM_PROFILE;
const urls = readFileSync(process.env.WM_URLS, 'utf-8').split('\n').map(s => s.trim()).filter(Boolean);

const ctx = await chromium.launchPersistentContext(PROFILE, {
  headless: false, viewport: { width: 1400, height: 900 }, locale: 'ru-RU',
  args: ['--disable-blink-features=AutomationControlled'],
});
const page = ctx.pages()[0] || (await ctx.newPage());
page.setDefaultTimeout(40000);

await page.goto('https://webmaster.yandex.ru/site/https:macmagia.ru:443/indexing/reindex/',
                { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(4000);
if (page.url().includes('passport')) {
  console.log('нужен вход в Яндекс — окно открыто, жду до 5 минут');
  for (let i = 0; i < 60 && page.url().includes('passport'); i++) await page.waitForTimeout(5000);
  await page.goto('https://webmaster.yandex.ru/site/https:macmagia.ru:443/indexing/reindex/',
                  { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
}

const quota = await page.evaluate(() => document.body.innerText.match(/[Оо]сталось[^\n]{0,60}/)?.[0] || '');
console.log('квота:', quota || 'не видно');

// Форма принимает список целиком: это textarea, а не поле по одному адресу.
const area = page.locator('textarea').first();
await area.fill(urls.join('\n'), { timeout: 15000 });
await page.waitForTimeout(1000);
const btn = page.getByRole('button', { name: /отправить|добавить|переобход/i }).first();
await btn.click({ timeout: 15000 }).catch((e) => console.log('кнопка:', String(e.message).slice(0, 80)));
await page.waitForTimeout(5000);
const body = await page.evaluate(() => document.body.innerText);
const note = body.match(/[^\n]*(отправлен|добавлен|очеред|лимит|исчерпан|превышен)[^\n]*/i);
console.log('адресов в списке:', urls.length);
console.log('ответ панели:', note ? note[0].trim().slice(0, 160) : 'без явного сообщения');
await page.screenshot({ path: process.env.WM_OUT ? `${process.env.WM_OUT}/recrawl.png` : 'recrawl.png' });
await ctx.close();
