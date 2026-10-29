(() => {
    const visual = document.querySelector('.result-visual');
    const summary = document.querySelector('.result-summary');
    const counts = summary?.querySelector('.result-ripeness-counts');
    const toolbar = visual?.querySelector('.result-visual-toolbar');
    if (!visual || !counts || !toolbar) return;

    const desktop = matchMedia('screen and (min-width: 1051px)');
    function alignImage() {
        if (!desktop.matches) {
            visual.style.removeProperty('--result-image-height');
            return;
        }
        // Use the toolbar rather than the animated figure to measure its top.
        const top = toolbar.getBoundingClientRect().bottom +
            parseFloat(getComputedStyle(toolbar).marginBottom);
        const help = visual.querySelector('.fruit-filter-help:not([hidden])');
        const helpHeight = help ? help.getBoundingClientRect().height +
            parseFloat(getComputedStyle(help).marginTop) +
            parseFloat(getComputedStyle(help).marginBottom) : 0;
        const height = Math.max(160, counts.getBoundingClientRect().bottom - top - helpHeight);
        visual.style.setProperty('--result-image-height', `${height}px`);
    }

    const observer = new ResizeObserver(alignImage);
    observer.observe(summary);
    observer.observe(toolbar);
    window.addEventListener('resize', alignImage);
    desktop.addEventListener('change', alignImage);
    document.fonts.ready.then(alignImage);
    alignImage();
})();
