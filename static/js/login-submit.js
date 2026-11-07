(() => {
    const form = document.getElementById('login-form');
    const button = form.querySelector('[type=submit]');
    const spinner = button.querySelector('.login-spinner');
    const label = document.getElementById('login-submit-label');
    const arrow = document.getElementById('login-submit-arrow');
    const status = document.getElementById('login-status');
    let busy = false;
    function reset() {
        busy = false;
        button.disabled = false;
        spinner.hidden = true;
        arrow.hidden = false;
        label.textContent = 'Sign In';
        form.removeAttribute('aria-busy');
        status.hidden = true;
    }
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (busy) return;
        busy = true;
        button.disabled = true;
        spinner.hidden = false;
        arrow.hidden = true;
        label.textContent = 'Signing in…';
        form.setAttribute('aria-busy', 'true');
        status.textContent = 'Signing in. Please wait…';
        status.hidden = false;
        document.querySelector('.registration-errors')?.remove();
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 30000);
        try {
            const response = await fetch(form.action, {
                method:'POST', body:new FormData(form), credentials:'same-origin',
                headers:{'X-Requested-With':'XMLHttpRequest'}, signal:controller.signal,
            });
            const result = await response.json();
            if (!response.ok || !result.redirect) {
                const messages = Object.values(result.errors || {}).flat().map(error => error.message);
                throw new Error(messages.join(' ') || 'Could not sign in. Please try again.');
            }
            label.textContent = 'Opening dashboard…';
            status.textContent = 'Signed in. Opening your account…';
            // Navigate the main window once, instead of loading the dashboard in
            // the popup first and then requesting it again in the main window.
            window.top.location.assign(result.redirect);
        } catch (error) {
            reset();
            const feedback = document.createElement('div');
            feedback.className = 'registration-errors';
            feedback.setAttribute('role', 'alert');
            feedback.textContent = error.name === 'AbortError' ? 'Sign in took too long. Please try again.' :
                (error instanceof SyntaxError || error instanceof TypeError ? 'Could not sign in. Please try again.' : error.message);
            form.before(feedback);
        } finally { clearTimeout(timeout); }
    });
    window.addEventListener('pageshow', reset);
})();
