(() => {
    const dropdown = document.getElementById('account-dropdown');
    if (!dropdown) return;
    document.addEventListener('click', event => {
        if (!dropdown.contains(event.target)) dropdown.open = false;
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && dropdown.open) {
            dropdown.open = false;
            dropdown.querySelector('summary').focus();
        }
    });
    dropdown.querySelector('.account-dropdown-links').addEventListener('click', event => {
        if (event.target.closest('a,button')) dropdown.open = false;
    });
})();
