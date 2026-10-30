(() => {
    const root = document.getElementById('multi-results');
    const track = document.getElementById('multi-result-track');
    if (!root || !track) return;
    const slides = [...track.querySelectorAll('.multi-result-slide')];
    const thumbnails = [...root.querySelectorAll('[data-slide]')];
    const previous = document.getElementById('multi-prev');
    const next = document.getElementById('multi-next');
    const position = document.getElementById('multi-position');
    const individual = document.getElementById('individual-result-mode');
    const caption = document.getElementById('multi-caption');
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    let active = 0;

    function update(index) {
        active = Math.max(0, Math.min(slides.length - 1, index));
        previous.disabled = active === 0;
        next.disabled = active === slides.length - 1;
        position.textContent = `${active + 1} / ${slides.length}`;
        individual.href = slides[active].dataset.individualUrl;
        caption.textContent = slides[active].dataset.caption;
        thumbnails.forEach((button, i) => button.setAttribute('aria-pressed', String(i === active)));
    }
    function move(index, instant = false) {
        update(index);
        track.scrollTo({left: slides[active].offsetLeft - slides[0].offsetLeft,
            behavior: instant || motion.matches ? 'instant' : 'smooth'});
    }
    previous.addEventListener('click', () => move(active - 1));
    next.addEventListener('click', () => move(active + 1));
    thumbnails.forEach(button => button.addEventListener('click', () => move(Number(button.dataset.slide))));
    track.addEventListener('keydown', event => {
        if (event.target !== track || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        move(event.key === 'Home' ? 0 : event.key === 'End' ? slides.length - 1 : active + (event.key === 'ArrowRight' ? 1 : -1));
    });
    let frame;
    track.addEventListener('scroll', () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
            if (track.clientWidth) update(Math.round(track.scrollLeft / track.clientWidth));
        });
    }, {passive: true});
    let lastWidth = track.clientWidth;
    new ResizeObserver(() => {
        if (track.clientWidth !== lastWidth) {
            lastWidth = track.clientWidth;
            move(active, true);
        }
    }).observe(track);
    const labels = document.getElementById('multi-toggle-labels');
    labels.addEventListener('click', () => {
        const shown = root.classList.toggle('labels-visible');
        labels.setAttribute('aria-pressed', String(shown));
        labels.textContent = shown ? labels.dataset.hide : labels.dataset.show;
    });
    root.querySelectorAll('button[data-ripeness]').forEach(button => {
        button.addEventListener('click', () => {
            const filter = button.dataset.ripeness;
            root.querySelectorAll('button[data-ripeness]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
            root.querySelectorAll('.bounding-box').forEach(box => {
                box.classList.toggle('fruit-dimmed', filter !== 'all' && box.dataset.ripeness !== filter);
            });
        });
    });
    const requested = location.hash.match(/^#scan-(\d+)$/);
    const initial = requested ? slides.findIndex(slide => slide.dataset.scanId === requested[1]) : 0;
    move(initial < 0 ? 0 : initial, true);
})();
