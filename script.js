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
