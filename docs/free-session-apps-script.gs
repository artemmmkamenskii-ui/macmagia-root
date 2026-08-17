/**
 * Приём заявок со страницы https://macmagia.ru/free-session/ в Google-таблицу.
 *
 * Куда вставлять: Google-таблица → Расширения → Apps Script → заменить весь Code.gs
 * на этот файл → Развернуть → Новое развёртывание → Веб-приложение
 * (Запуск от имени: я; Доступ: все) → скопировать URL и вставить в
 * free-session/index.html в переменную ENDPOINT.
 *
 * Пошаговая инструкция: docs/free-session-google-sheets.md
 */

var SHEET_NAME = 'Заявки';

var HEADERS = [
  'Дата и время (МСК)',
  'Имя',
  'Телефон',
  'Запрос',
  'Блок рассылки',
  'Статус',
  'Кто взял',
  'Источник',
  'Заметки'
];

function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
  } catch (err) {
    return jsonResponse({ ok: false, error: 'busy' });
  }

  try {
    var data = parseRequest(e);

    // Ловушка для ботов: живой человек это поле не видит и не заполняет.
    if (text(data.company)) {
      return jsonResponse({ ok: true, skipped: 'spam' });
    }

    /* Одна и та же заявка может прийти дважды: страница переотправляет её,
       если не смогла прочитать ответ. Номер заявки (uid) держим 10 минут
       в кэше — повтор с тем же номером в таблицу не попадёт. */
    var uid = text(data.uid, 60);
    var cache = CacheService.getScriptCache();
    if (uid) {
      if (cache.get('lead_' + uid)) {
        return jsonResponse({ ok: true, skipped: 'duplicate' });
      }
      cache.put('lead_' + uid, '1', 600);
    }

    var name = text(data.name, 100);
    var phone = text(data.phone, 50);

    if (!name || !phone) {
      return jsonResponse({ ok: false, error: 'empty' });
    }

    getSheet().appendRow([
      Utilities.formatDate(new Date(), 'Europe/Moscow', 'dd.MM.yyyy HH:mm'),
      name,
      phone,
      text(data.request, 2000),
      text(data.topic, 100),
      'Новая',
      '',
      buildSource(data),
      ''
    ]);

    return jsonResponse({ ok: true });
  } catch (err) {
    console.error(err);
    return jsonResponse({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

/** Открыть URL веб-приложения в браузере — быстрая проверка, что оно живо. */
function doGet() {
  return jsonResponse({ ok: true, service: 'macmagia free-session', rows: getSheet().getLastRow() - 1 });
}

function parseRequest(e) {
  if (e && e.postData && e.postData.contents) {
    try {
      return JSON.parse(e.postData.contents);
    } catch (err) {
      // Не JSON — значит, форма ушла обычным urlencoded-запросом.
    }
  }
  return (e && e.parameter) || {};
}

function buildSource(data) {
  var parts = [];
  if (text(data.page)) parts.push(text(data.page, 200));
  if (text(data.referrer)) parts.push('откуда: ' + text(data.referrer, 200));
  return parts.join(' | ');
}

function text(value, limit) {
  var s = String(value == null ? '' : value).trim();
  return limit && s.length > limit ? s.slice(0, limit) + '…' : s;
}

function getSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(HEADERS);
    sheet.getRange(1, 1, 1, HEADERS.length)
      .setFontWeight('bold')
      .setBackground('#ede8ff');
    sheet.setFrozenRows(1);
    sheet.setColumnWidth(1, 140); // дата
    sheet.setColumnWidth(2, 140); // имя
    sheet.setColumnWidth(3, 160); // телефон
    sheet.setColumnWidth(4, 420); // запрос
    sheet.setColumnWidth(5, 170); // блок рассылки
    sheet.setColumnWidth(8, 260); // источник
  }

  return sheet;
}

function jsonResponse(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}
