document.addEventListener('DOMContentLoaded', () => {
    const language = document.getElementById('language-choice');
    document.getElementById('save-language').hidden = true;
    language.addEventListener('change', () => language.form.requestSubmit());
    const toggle = document.getElementById('darkModeToggle');
    const state = document.getElementById('theme-state');
    const updateState = () => { state.textContent = toggle.checked ? state.dataset.on : state.dataset.off; };
    updateState(); toggle.addEventListener('change', updateState);
    const modal = document.getElementById('passwordModal');
    const opener = document.getElementById('open-password');
    let previousFocus = opener;
    function open() {
        previousFocus = document.activeElement;
        modal.style.display = 'flex';
        modal.querySelector('input:not([type=hidden])')?.focus();
    }
    function close() { modal.style.display = 'none'; previousFocus?.focus(); }
    opener.addEventListener('click', open);
    modal.querySelector('.close-modal').onclick = close;
    modal.addEventListener('click', event => { if (event.target === modal) close(); });
    modal.addEventListener('keydown', event => {
        if (event.key === 'Escape') close();
        if (event.key !== 'Tab') return;
        const targets = [...modal.querySelectorAll('button, input:not([type=hidden])')];
        const first = targets[0], last = targets[targets.length-1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    if (location.hash === '#passwordModal' || modal.style.display === 'flex') open();
});
