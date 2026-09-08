// Подсказка про VPN: показывается, только если стили не доехали за 8 секунд.
// Сам HTML при этом уже пришёл — значит человек видит голый текст и думает,
// что сайт сломан. Полный таймаут этим не лечится: там показывать нечего.
(function () {
  var shown = false;
  function cssLoaded() {
    for (var i = 0; i < document.styleSheets.length; i++) {
      try {
        var s = document.styleSheets[i];
        if (s.href && s.href.indexOf('styles.css') > -1 && s.cssRules && s.cssRules.length) return true;
      } catch (e) { return true; }  // кросс-доменный лист читать нельзя, но он загружен
    }
    return false;
  }
  function show() {
    if (shown || cssLoaded()) return;
    shown = true;
    var d = document.createElement('div');
    d.setAttribute('role', 'status');
    d.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:99999;padding:14px 16px;'
      + 'background:#2b2b33;color:#fff;font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;'
      + 'display:flex;gap:12px;align-items:center;justify-content:center;flex-wrap:wrap';
    d.innerHTML = '<span>Страница загружается медленно. Если вы пользуетесь VPN, попробуйте его отключить '
      + 'или сменить страну — так сайт откроется быстрее.</span>'
      + '<button type="button" style="background:#fff;color:#2b2b33;border:0;border-radius:6px;'
      + 'padding:7px 14px;font:inherit;cursor:pointer">Понятно</button>';
    d.querySelector('button').onclick = function () { d.remove(); };
    document.body.appendChild(d);
  }
  setTimeout(show, 8000);
})();
