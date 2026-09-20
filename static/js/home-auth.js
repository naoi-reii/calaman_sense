(() => {
    const dialog = document.getElementById('auth-dialog');
    const frame = document.getElementById('auth-frame');
    let opener = null;
    function close() {
        dialog.close(); document.body.classList.remove('auth-popup-open');
        frame.removeAttribute('src'); opener?.focus();
    }
    document.querySelectorAll('a[href="/login/"], a[href="/register/"]').forEach(link => {
        link.addEventListener('click', event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            event.preventDefault(); opener = link;
            frame.src = link.href; dialog.showModal(); document.body.classList.add('auth-popup-open');
        });
    });
    document.getElementById('close-auth').addEventListener('click', close);
    dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    dialog.addEventListener('click', event => { if (event.target === dialog) close(); });
    window.addEventListener('message', event => {
        if (event.origin === location.origin && event.source === frame.contentWindow && event.data?.type === 'close-auth') close();
    });
    frame.addEventListener('load', () => {
        if (!dialog.open || !frame.getAttribute('src')) return;
        try {
            const url = new URL(frame.contentWindow.location.href);
            if (url.origin !== location.origin) return;
            if (url.pathname === '/') { close(); return; }
            if (!['/login/', '/register/'].includes(url.pathname)) window.location.assign(url.href);
        } catch (_) { /* Browser enforces the same-origin boundary. */ }
    });
})();
