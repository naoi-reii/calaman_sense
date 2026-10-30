document.addEventListener('submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !matchMedia('(max-width:760px)').matches) return;
    if (new URL(form.action, location.href).pathname !== '/logout/') return;
    let destination = form.querySelector('input[name="next"]');
    if (!destination) {
        destination = document.createElement('input');
        destination.type = 'hidden';
        destination.name = 'next';
        form.append(destination);
    }
    destination.value = '/login/?logged_out=1';
}, true);
