import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'fs';
const OUT='/tmp/metrika3'; mkdirSync(OUT,{recursive:true});
const ctx = await chromium.launchPersistentContext(process.env.WM_PROFILE, {
  channel:'chrome', headless:false, viewport:{width:1600,height:1000}, locale:'ru-RU' });
const page = ctx.pages()[0] || (await ctx.newPage());
page.setDefaultTimeout(45000);
await page.goto('https://metrika.yandex.ru/dashboard?id=109562142&period=week', {waitUntil:'domcontentloaded'});
await page.waitForTimeout(10000);
// адреса отчётов берём из меню, а не угадываем
const links = await page.evaluate(() =>
  [...document.querySelectorAll('a[href*="/stat/"], a[href*="/list/"]')]
    .map(a => ({href:a.getAttribute('href'), text:a.innerText.trim().slice(0,40)}))
    .filter(x => x.href && x.text));
const uniq=[...new Map(links.map(l=>[l.href,l])).values()].slice(0,14);
console.log('ссылок в меню:', uniq.length);
uniq.forEach(l=>console.log('  ', l.text, '→', l.href.slice(0,70)));
await ctx.close();
