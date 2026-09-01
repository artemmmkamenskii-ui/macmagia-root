// Footer year
const yearEl = document.getElementById('year');
if (yearEl) yearEl.textContent = new Date().getFullYear();

// Mobile nav toggle
const burger = document.querySelector('.burger');
const nav = document.querySelector('.nav');
if (burger && nav) {
    burger.addEventListener('click', () => {
        nav.classList.toggle('nav--open');
    });
    nav.querySelectorAll('a').forEach(a =>
        a.addEventListener('click', () => nav.classList.remove('nav--open'))
    );
    document.addEventListener('click', (e) => {
        if (!nav.contains(e.target) && !burger.contains(e.target)) {
            nav.classList.remove('nav--open');
        }
    });
}

// Reading progress bar (only present on article pages)
const progressFill = document.querySelector('.reading-progress__fill');
if (progressFill) {
    let ticking = false;
    const update = () => {
        const h = document.documentElement;
        const max = h.scrollHeight - h.clientHeight;
        const pct = max > 0 ? Math.min(100, (h.scrollTop / max) * 100) : 0;
        progressFill.style.width = pct + '%';
        ticking = false;
    };
    update();
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(update);
            ticking = true;
        }
    }, { passive: true });
    window.addEventListener('resize', update);
}

// Клики по кнопкам ботов -> цели в Метрике
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.article__subscribe-btn');
    if (!btn) return;
    const goal = btn.classList.contains('article__subscribe-btn--tg') ? 'bot_tg'
        : btn.classList.contains('article__subscribe-btn--max') ? 'bot_max'
        : null;
    if (goal && window.ym) ym(109562142, 'reachGoal', goal, { page: location.pathname });
});
