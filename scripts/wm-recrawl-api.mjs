// Переобход через API Яндекс.Вебмастера — без браузера.
//
// Зачем: интерфейсная отправка (wm-recrawl.mjs) требует живой сессии и
// открытого окна, то есть человека рядом. Лимит переобхода при этом упал
// со 150 адресов в сутки до 10, и очередь в полторы сотни статей вручную
// не разослать: про неё просто забывают между заходами.
//
// Токен берётся из ~/.config/provizorai/yandex-oauth.env (вне git), скрипт
// его не печатает. Нужен скоуп webmaster:hostinfo + webmaster:verify.
//
//   node scripts/wm-recrawl-api.mjs                 # 10 адресов из очереди
//   WM_LIMIT=5 node scripts/wm-recrawl-api.mjs      # сколько слать
//   WM_URLS=/tmp/list.txt node scripts/wm-recrawl-api.mjs   # свой список
//   WM_DRY=1 node scripts/wm-recrawl-api.mjs        # показать и не слать
//
// Очередь — файл docs/seo/recrawl-queue.txt, по адресу на строку.
// Отправленные вычёркиваются, так что запускать можно хоть ежедневно.

import { readFileSync, writeFileSync, existsSync, appendFileSync } from 'fs';
import { homedir } from 'os';
import { join } from 'path';

const ENV_FILE = process.env.WM_ENV || join(homedir(), '.config/provizorai/yandex-oauth.env');
const QUEUE = process.env.WM_URLS || 'docs/seo/recrawl-queue.txt';
const SENT_LOG = 'docs/seo/recrawl-sent.log';
// В API сайт зовётся с завершающим слешем, а не как в адресе панели
// (там host_id вида https:macmagia.ru:443). Не угадывать: список отдаёт
// /user/<id>/hosts/, и при промахе скрипт печатает доступные варианты.
const HOST = process.env.WM_HOST || 'https://macmagia.ru/';
const LIMIT = Number(process.env.WM_LIMIT || 10);
const DRY = !!process.env.WM_DRY;

function token() {
  if (process.env.YANDEX_OAUTH_TOKEN) return process.env.YANDEX_OAUTH_TOKEN;
  if (!existsSync(ENV_FILE)) throw new Error(`нет файла с токеном: ${ENV_FILE}`);
  for (const line of readFileSync(ENV_FILE, 'utf-8').split('\n')) {
    const m = line.match(/^\s*YANDEX_OAUTH_TOKEN\s*=\s*(.+?)\s*$/);
    if (m) return m[1].replace(/^["']|["']$/g, '');
  }
  throw new Error('YANDEX_OAUTH_TOKEN не найден в ' + ENV_FILE);
}

const TOKEN = token();
const api = async (path, init = {}) => {
  const r = await fetch('https://api.webmaster.yandex.net/v4' + path, {
    ...init,
    headers: { Authorization: `OAuth ${TOKEN}`, 'Content-Type': 'application/json', ...(init.headers || {}) },
  });
  const text = await r.text();
  let body;
  try { body = JSON.parse(text); } catch { body = text; }
  return { ok: r.ok, status: r.status, body };
};

// 1. кто мы и какой сайт
const me = await api('/user/');
if (!me.ok) {
  console.error('токен не принят:', me.status, JSON.stringify(me.body).slice(0, 200));
  console.error('нужен скоуп webmaster:hostinfo + webmaster:verify — перевыпустите токен.');
  process.exit(2);
}
const userId = me.body.user_id;

const hosts = await api(`/user/${userId}/hosts/`);
if (!hosts.ok) { console.error('не читается список сайтов:', hosts.status); process.exit(2); }
const host = (hosts.body.hosts || []).find(h => h.ascii_host_url === HOST || h.unicode_host_url === HOST);
if (!host) {
  console.error('сайт не найден. Доступные:', (hosts.body.hosts || []).map(h => h.ascii_host_url).join(', '));
  process.exit(2);
}

// 2. сколько сегодня можно
const quota = await api(`/user/${userId}/hosts/${host.host_id}/recrawl/quota/`);
const left = quota.ok ? quota.body.quota_remainder : null;
console.log('сайт:', host.ascii_host_url, '| осталось в квоте:', left ?? 'неизвестно');

// 3. очередь
if (!existsSync(QUEUE)) { console.error(`нет очереди: ${QUEUE}`); process.exit(1); }
const all = readFileSync(QUEUE, 'utf-8').split('\n').map(s => s.trim()).filter(Boolean);
const take = Math.min(LIMIT, left ?? LIMIT, all.length);
const batch = all.slice(0, take);
console.log(`в очереди ${all.length}, отправляю ${batch.length}`);
if (!batch.length) process.exit(0);
if (DRY) { batch.forEach(u => console.log('  (сухой прогон)', u)); process.exit(0); }

// 4. отправка
const sent = [];
for (const url of batch) {
  const r = await api(`/user/${userId}/hosts/${host.host_id}/recrawl/queue/`, {
    method: 'POST', body: JSON.stringify({ url }),
  });
  if (r.ok) { sent.push(url); console.log('  ✓', url); }
  else {
    const why = JSON.stringify(r.body).slice(0, 120);
    console.log('  ×', url, r.status, why);
    // квота кончилась — остальное оставляем в очереди на завтра
    if (/QUOTA/i.test(why)) break;
  }
}

// 5. вычеркнуть отправленное
const rest = all.filter(u => !sent.includes(u));
writeFileSync(QUEUE, rest.length ? rest.join('\n') + '\n' : '');
if (sent.length) {
  const stamp = new Date().toISOString().slice(0, 10);
  appendFileSync(SENT_LOG, sent.map(u => `${stamp} ${u}`).join('\n') + '\n');
}
console.log(`отправлено ${sent.length}, осталось в очереди ${rest.length}`);
