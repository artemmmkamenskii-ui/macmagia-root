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

var VERSION = 'v4-phone-8';

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
    var phone = normalizePhone(data.phone);

    if (!name || !phone) {
      return jsonResponse({ ok: false, error: 'empty' });
    }

    var sheet = getSheet();
    var row = sheet.getLastRow() + 1;

    /* Телефон «+7 900…» и всё, что начинается с + или =, таблица принимает
       за формулу и показывает #ERROR!. Поэтому колонки со свободным текстом
       переводим в текстовый формат до записи. */
    sheet.getRange(row, 2, 1, HEADERS.length - 1).setNumberFormat('@');

    sheet.getRange(row, 1, 1, HEADERS.length).setValues([[
      Utilities.formatDate(new Date(), 'Europe/Moscow', 'dd.MM.yyyy HH:mm'),
      name,
      phone,
      text(data.request, 2000),
      text(data.topic, 100),
      'Новая',
      '',
      buildSource(data),
      ''
    ]]);

    // Страховка: если телефон всё-таки стал формулой — переписываем ячейку текстом.
    var phoneCell = sheet.getRange(row, 3);
    if (phoneCell.getDisplayValue().charAt(0) === '#') {
      phoneCell.setNumberFormat('@');
      phoneCell.setValue(phone);
    }

    return jsonResponse({ ok: true });
  } catch (err) {
    console.error(err);
    return jsonResponse({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

/** Открыть URL веб-приложения в браузере — быстрая проверка, что оно живо.
 *  VERSION меняется вместе с кодом: по нему видно, какая версия развёрнута.
 *  Телефон наружу не отдаём — только признак, текст в ячейке или ошибка. */
function doGet() {
  var sheet = getSheet();
  var last = sheet.getLastRow();
  var out = {
    ok: true,
    service: 'macmagia free-session',
    version: VERSION,
    rows: last - 1
  };

  if (last > 1) {
    var shown = sheet.getRange(last, 3).getDisplayValue();
    out.lastPhoneOk = shown.charAt(0) !== '#';
  }

  return jsonResponse(out);
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

/**
 * Телефон приводим к виду без ведущего плюса: «+7 900 …» → «8 900 …».
 * Со знака + таблица начинает считать ячейку формулой и рисует #ERROR!.
 * Иностранный номер просто теряет плюс: «+380 …» → «380 …».
 */
function normalizePhone(value) {
  var s = text(value, 50);
  if (s.charAt(0) !== '+') return s;

  s = s.slice(1).replace(/^\s+/, '');
  return s.charAt(0) === '7' ? '8' + s.slice(1) : s;
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
    // Со второй строки и ниже — текстовый формат, чтобы телефоны не стали формулами.
    sheet.getRange(2, 2, sheet.getMaxRows() - 1, HEADERS.length - 1).setNumberFormat('@');
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
