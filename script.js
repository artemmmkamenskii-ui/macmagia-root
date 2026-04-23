// Footer year
document.getElementById('year').textContent = new Date().getFullYear();

// Mobile nav toggle
const burger = document.querySelector('.burger');
const nav = document.querySelector('.nav');
if (burger && nav) {
    burger.addEventListener('click', () => {
        const open = nav.classList.toggle('nav--open');
        if (open) {
            nav.style.display = 'flex';
            nav.style.position = 'absolute';
            nav.style.top = '100%';
            nav.style.left = '0';
            nav.style.right = '0';
            nav.style.flexDirection = 'column';
            nav.style.background = '#fff';
            nav.style.padding = '16px 24px';
            nav.style.borderBottom = '1px solid #ece8f5';
            nav.style.boxShadow = '0 10px 30px rgba(110, 80, 200, .10)';
        } else {
            nav.removeAttribute('style');
        }
    });
    nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
        nav.classList.remove('nav--open');
        nav.removeAttribute('style');
    }));
}
