(() => {
    const root = document.documentElement;
    const deviceTheme = matchMedia('(prefers-color-scheme: dark)');
    const storageValues = {light: 'disabled', dark: 'enabled', system: 'system'};
    function readPreference() {
        try {
            const saved = localStorage.getItem('darkMode');
            if (saved === 'enabled') return 'dark';
            if (saved === 'disabled') return 'light';
        } catch (_) {}
        return 'system';
    }
    let preference = readPreference();
    function apply() {
        const dark = preference === 'dark' || (preference === 'system' && deviceTheme.matches);
        root.dataset.theme = dark ? 'dark' : 'light';
        root.dataset.themePreference = preference;
        root.style.colorScheme = dark ? 'dark' : 'light';
        document.querySelectorAll('#darkModeToggle').forEach(input => { input.checked = dark; });
        document.querySelectorAll('[name="appearance"]').forEach(input => {
            input.checked = input.value === preference;
        });
    }
    function setPreference(value) {
        if (!Object.hasOwn(storageValues, value)) return;
        preference = value;
        try { localStorage.setItem('darkMode', storageValues[value]); } catch (_) {}
        apply();
    }
    // No saved choice means follow the device, applied before the page paints.
    apply();
    document.addEventListener('DOMContentLoaded', () => {
        apply();
        document.getElementById('darkModeToggle')?.addEventListener('change', event => {
            setPreference(event.target.checked ? 'dark' : 'light');
        });
        document.querySelectorAll('[name="appearance"]').forEach(input => {
            input.addEventListener('change', () => {
                if (input.checked) setPreference(input.value);
            });
        });
    });
    deviceTheme.addEventListener('change', () => {
        if (preference === 'system') apply();
    });
    window.addEventListener('storage', event => {
        if (event.key === 'darkMode' || event.key === null) {
            preference = readPreference();
            apply();
        }
    });
    window.addEventListener('pageshow', () => {
        preference = readPreference();
        apply();
    });
})();
