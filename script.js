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
