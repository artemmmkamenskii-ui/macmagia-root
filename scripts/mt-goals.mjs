import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'fs';
const OUT='/tmp/metrika4'; mkdirSync(OUT,{recursive:true});
const ctx = await chromium.launchPersistentContext(process.env.WM_PROFILE, {
  channel:'chrome', headless:false, viewport:{width:1600,height:1000}, locale:'ru-RU' });
const page = ctx.pages()[0] || (await ctx.newPage());
page.setDefaultTimeout(50000);
const ID='109562142';
// названия отчётов кликаем в интерфейсе: прямые адреса у Метрики разъехались
const want = [['Источники','Источники, сводка'], ['Страницы входа','Страницы входа'], ['Конверсии','Конверсии']];
await page.goto(`https://metrika.yandex.ru/stat/conversion_rate?id=${ID}&period=week`, {waitUntil:'domcontentloaded'});
await page.waitForTimeout(14000);
let txt = await page.evaluate(()=>document.body.innerText);
writeFileSync(`${OUT}/celi.txt`, txt, 'utf-8');
console.log('цели/конверсии:', txt.length, 'знаков');
const rows = await page.evaluate(()=>[...document.querySelectorAll('table tr')].slice(0,20)
  .map(tr=>[...tr.querySelectorAll('td,th')].map(c=>c.innerText.replace(/\n+/g,' ').trim()).filter(Boolean).join(' | ')).filter(Boolean));
console.log(rows.slice(0,12).join('\n'));
await ctx.close();
