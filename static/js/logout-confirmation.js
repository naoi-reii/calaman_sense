(() => {
    const dialog = document.getElementById('logout-confirmation');
    if (!dialog) return;
    let selected = null, opener = null;
    const approved = new WeakSet();
    document.addEventListener('submit', event => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || new URL(form.action, location.href).pathname !== '/logout/') return;
        if (approved.has(form)) { approved.delete(form); return; }
        event.preventDefault();
        event.stopImmediatePropagation();
        if (dialog.open) return;
        selected = {form, submitter:event.submitter};
        opener = document.activeElement;
        dialog.showModal();
    }, true);
    function dismiss() {
        dialog.close(); selected = null;
        opener?.focus({preventScroll:true});
    }
    document.getElementById('logout-stay').addEventListener('click', dismiss);
    dialog.addEventListener('cancel', event => { event.preventDefault(); dismiss(); });
    document.getElementById('logout-confirm').addEventListener('click', () => {
        if (!selected) return;
        const {form, submitter} = selected;
        dialog.close(); selected = null;
        approved.add(form);
        if (submitter) form.requestSubmit(submitter); else form.requestSubmit();
    });
})();
