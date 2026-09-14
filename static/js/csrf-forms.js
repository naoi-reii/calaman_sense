/* Login rotates Django's CSRF secret, including in other tabs. */
(() => {
    function refreshForm(form) {
        if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== 'post') return;
        if (new URL(form.action, location.href).origin !== location.origin) return;
        const cookie = document.cookie.split(';').map(part => part.trim())
            .find(part => part.startsWith('csrftoken='));
        if (!cookie) return; // Preserve the server token if cookies are unavailable.
        const token = cookie.slice('csrftoken='.length);
        if (!/^[a-zA-Z0-9]{32}$/.test(token)) return;
        form.querySelectorAll('input[name="csrfmiddlewaretoken"]').forEach(input => {
            input.value = token;
        });
    }
    function refreshForms() { document.querySelectorAll('form').forEach(refreshForm); }
    // Capture runs before existing form submit handlers construct their payloads.
    document.addEventListener('submit', event => refreshForm(event.target), true);
    window.addEventListener('pageshow', refreshForms);
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') refreshForms();
    });
    refreshForms();
})();
