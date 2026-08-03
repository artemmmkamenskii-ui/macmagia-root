/* Психологические тесты на страницах блога.
 *
 * Подсчёт идёт по двум независимым шкалам, тип определяется их пересечением
 * (см. docs/seo/tests/<id>.yaml). Тексты результатов лежат в самой статье
 * заголовками с якорями — скрипт только подсвечивает нужный и ведёт к нему.
 */
(function () {
  var root = document.getElementById('quiz');
  if (!root) return;

  var cfg = JSON.parse(root.getAttribute('data-cfg'));
  var bar = document.getElementById('quiz-bar');
  var done = document.getElementById('quiz-done');
  var go = document.getElementById('quiz-go');
  var box = document.getElementById('quiz-result');
  var titleEl = document.getElementById('quiz-title');
  var scalesEl = document.getElementById('quiz-scales');
  var jump = document.getElementById('quiz-jump');
  var again = document.getElementById('quiz-again');

  function answered() {
    return root.querySelectorAll('.quiz__q input:checked').length;
  }

  function refresh() {
    var n = answered();
    done.textContent = n;
    bar.style.width = (n / cfg.total * 100) + '%';
    go.disabled = n < cfg.total;
  }

  root.addEventListener('change', function (e) {
    if (e.target.type !== 'radio') return;
    e.target.closest('.quiz__q').classList.add('quiz__q--done');
    refresh();
    // подводим к следующему неотвеченному вопросу
    var next = root.querySelector('.quiz__q:not(.quiz__q--done)');
    if (next) next.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });

  function score() {
    var s = {};
    root.querySelectorAll('.quiz__q input:checked').forEach(function (i) {
      var k = i.getAttribute('data-scale');
      var v = parseInt(i.value, 10);
      // обратное утверждение: согласие означает НИЗКИЙ балл по шкале,
      // поэтому значение инвертируется. Так гасится склонность
      // соглашаться со всем подряд, которая иначе завышает все шкалы.
      if (i.getAttribute('data-reverse')) v = (cfg.maxOption || 3) - v;
      s[k] = (s[k] || 0) + v;
    });
    return s;
  }

  function pick(s) {
    // режим «axes»: четыре бинарные оси, результат — код из четырёх букв
    if (cfg.mode === 'axes') {
      var code = cfg.axes.map(function (ax) {
        var a = s[ax.key + '_' + ax.poles[0]] || 0;
        var b = s[ax.key + '_' + ax.poles[1]] || 0;
        return a >= b ? ax.poles[0] : ax.poles[1];
      }).join('').toLowerCase();
      for (var q = 0; q < cfg.results.length; q++) {
        if (cfg.results[q].key === code) return cfg.results[q];
      }
      return cfg.results[0];
    }
    // режим «top»: результат — шкала с максимальным баллом (архетипы и т.п.)
    if (cfg.mode === 'top') {
      var best = null;
      Object.keys(s).forEach(function (k) { if (!best || s[k] > s[best]) best = k; });
      for (var j = 0; j < cfg.results.length; j++) {
        if (cfg.results[j].scale === best) return cfg.results[j];
      }
      return cfg.results[0];
    }
    var hi = {};
    // строго больше середины: ровно середина = нет выраженного предпочтения,
    // и в спорной точке мы не приписываем человеку проблемный полюс
    Object.keys(s).forEach(function (k) { hi[k] = s[k] > cfg.threshold ? 'high' : 'low'; });
    for (var i = 0; i < cfg.results.length; i++) {
      var r = cfg.results[i], ok = true;
      Object.keys(hi).forEach(function (k) { if (r[k] && r[k] !== hi[k]) ok = false; });
      if (ok) return r;
    }
    return cfg.results[0];
  }

  function setupShare(res) {
    var url = location.origin + location.pathname + '?r=' + res.key;
    var head = (root.querySelector('.quiz__result-head') || {}).textContent || 'Мой результат';
    var text = head.replace(/^Ваш/, 'Мой') + ' — ' + res.title + '. А какой у вас?';
    var u = encodeURIComponent(url), tx = encodeURIComponent(text);

    var links = {
      'share-vk': 'https://vk.com/share.php?url=' + u + '&title=' + tx,
      'share-tg': 'https://t.me/share/url?url=' + u + '&text=' + tx,
      'share-wa': 'https://api.whatsapp.com/send?text=' + encodeURIComponent(text + ' ' + url),
      'share-ok': 'https://connect.ok.ru/offer?url=' + u + '&title=' + tx
    };
    Object.keys(links).forEach(function (id) {
      var el = document.getElementById(id);
      if (!el) return;
      el.setAttribute('href', links[id]);
      el.onclick = function () { if (window.ym) ym(109562142, 'reachGoal', id.replace('-', '_')); };
    });

    var copy = document.getElementById('share-copy');
    if (copy) {
      copy.onclick = function () {
        var done = function () {
          var was = copy.textContent;
          copy.textContent = 'Ссылка скопирована';
          copy.classList.add('is-done');
          setTimeout(function () { copy.textContent = was; copy.classList.remove('is-done'); }, 2000);
          if (window.ym) ym(109562142, 'reachGoal', 'share_copy');
        };
        if (navigator.clipboard) {
          navigator.clipboard.writeText(url).then(done, done);
        } else {
          var i = document.createElement('input');
          i.value = url; document.body.appendChild(i); i.select();
          try { document.execCommand('copy'); } catch (e) {}
          document.body.removeChild(i); done();
        }
      };
    }
  }

  function show(res, s) {
    titleEl.textContent = res.title;
    if (cfg.mode === 'axes') {
      scalesEl.innerHTML = cfg.axes.map(function (ax) {
        var a = s[ax.key + '_' + ax.poles[0]] || 0;
        var b = s[ax.key + '_' + ax.poles[1]] || 0;
        var win = a >= b ? 0 : 1;
        // полоска заполняется со стороны победившего полюса, иначе при
        // победе правого она выглядит пустой
        var pct = Math.round((win === 0 ? a : b) / (a + b || 1) * 100);
        return '<div class="quiz__axis">' +
          '<span class="' + (win === 0 ? 'is-win' : '') + '">' + ax.labels[0] + '</span>' +
          '<i class="' + (win === 1 ? 'is-right' : '') + '"><b style="width:' + pct + '%"></b></i>' +
          '<span class="' + (win === 1 ? 'is-win' : '') + '">' + ax.labels[1] + '</span>' +
          '</div>';
      }).join('');
    } else {
    var keys = Object.keys(s);
    if (cfg.mode === 'top') {
      keys.sort(function (a, b) { return s[b] - s[a]; });
      keys = keys.slice(0, 3);
    }
    scalesEl.innerHTML = keys.map(function (k) {
      var label = (cfg.scaleLabels && cfg.scaleLabels[k]) || k;
      var max = cfg.mode === 'top' ? (cfg.scaleMax || cfg.threshold * 2) : cfg.threshold * 2;
      var pct = Math.round(s[k] / max * 100);
      return '<div class="quiz__scale"><span>' + label + '</span>' +
        '<i><b style="width:' + Math.min(pct, 100) + '%"></b></i>' +
        '<em>' + s[k] + '</em></div>';
    }).join('');
    }
    jump.setAttribute('href', '#' + res.key);
    setupShare(res);
    box.hidden = false;

    // подсветить нужный разбор в тексте статьи
    var target = document.getElementById(res.key);
    var head = target && target.closest('h3');
    if (head) head.classList.add('article__result--mine');

    // адрес с результатом — чтобы можно было поделиться
    if (window.history && history.replaceState) {
      history.replaceState(null, '', '?r=' + res.key);
    }
    if (window.ym) ym(109562142, 'reachGoal', 'quiz_done_' + res.key);
    box.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  go.addEventListener('click', function () {
    var s = score();
    show(pick(s), s);
  });

  again.addEventListener('click', function () {
    root.querySelectorAll('input:checked').forEach(function (i) { i.checked = false; });
    root.querySelectorAll('.quiz__q--done').forEach(function (q) { q.classList.remove('quiz__q--done'); });
    document.querySelectorAll('.article__result--mine').forEach(function (h) {
      h.classList.remove('article__result--mine');
    });
    box.hidden = true;
    if (window.history && history.replaceState) history.replaceState(null, '', location.pathname);
    refresh();
    root.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  // пришли по ссылке с чужим результатом — сразу подсветим разбор
  var shared = (location.search.match(/[?&]r=([a-z-]+)/) || [])[1];
  if (shared) {
    var h = document.getElementById(shared);
    if (h && h.closest('h3')) h.closest('h3').classList.add('article__result--mine');
  }

  refresh();
})();
