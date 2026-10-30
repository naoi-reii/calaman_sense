(() => {
    const track = document.getElementById('group-image-track');
    if (!track) return;
    const slides = [...track.querySelectorAll('.result-figure')];
    const thumbnails = [...document.querySelectorAll('[data-group-slide]')];
    const previous = document.getElementById('group-image-prev');
    const next = document.getElementById('group-image-next');
    const individual = document.getElementById('group-individual-result');
    const position = document.getElementById('group-image-position');
    const caption = document.getElementById('group-image-caption');
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    let active = 0;
    function update(index) {
        active = Math.max(0, Math.min(slides.length - 1, index));
        previous.disabled = active === 0;
        next.disabled = active === slides.length - 1;
        individual.href = slides[active].dataset.resultUrl;
        caption.textContent = slides[active].dataset.caption;
        position.textContent = `${active + 1} / ${slides.length}`;
        thumbnails.forEach((button, i) => button.setAttribute('aria-pressed', String(active === i)));
    }
    function move(index, instant = false) {
        update(index);
        track.scrollTo({left: slides[active].offsetLeft - slides[0].offsetLeft,
            behavior: instant || motion.matches ? 'instant' : 'smooth'});
    }
    previous.addEventListener('click', () => move(active - 1));
    next.addEventListener('click', () => move(active + 1));
    thumbnails.forEach(button => button.addEventListener('click', () => move(Number(button.dataset.groupSlide))));
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
    let width = track.clientWidth;
    new ResizeObserver(() => {
        if (track.clientWidth !== width) {
            width = track.clientWidth;
            move(active, true);
        }
    }).observe(track);
    const requested = location.hash.match(/^#scan-(\d+)$/);
    const index = requested ? slides.findIndex(slide => slide.dataset.scanId === requested[1]) : 0;
    move(Math.max(0, index), true);
})();
