(() => {
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const animations = new Set(), counters = new Map();
    let observer;
    function finish() {
        observer?.disconnect();
        animations.forEach(animation => animation.cancel());
        animations.clear();
        counters.forEach((state, element) => {
            cancelAnimationFrame(state.frame);
            element.textContent = state.original;
        });
        counters.clear();
    }
    function animate(element, frames, delay = 0, duration = 650) {
        if (motion.matches || !element.animate) return;
        const animation = element.animate(frames, {duration, delay, fill: 'backwards', easing: 'cubic-bezier(.22,1,.36,1)'});
        animations.add(animation);
        animation.finished.catch(() => {}).finally(() => animations.delete(animation));
    }
    function count(element) {
        const target = Number(element.dataset.count);
        if (!Number.isFinite(target) || target <= 0) return;
        const state = {original: element.textContent, start: performance.now(), frame: 0};
        counters.set(element, state);
        function tick(now) {
            const progress = Math.min((now - state.start) / 1100, 1);
            element.textContent = Math.round(target * (1 - (1 - progress) ** 3)).toLocaleString();
            if (progress < 1) state.frame = requestAnimationFrame(tick);
            else { element.textContent = state.original; counters.delete(element); }
        }
        state.frame = requestAnimationFrame(tick);
    }
    function reveal(element) {
        if (motion.matches) return;
        if (element.matches('.result-figure')) {
            const boxes = [...element.querySelectorAll('.bounding-box')];
            boxes.forEach((box, index) => {
                // Bound the delay even for large batches.
                animate(box, [{opacity: 0, transform: 'scale(.88)'}, {opacity: 1, transform: 'scale(1)'}], index * Math.min(65, 900 / Math.max(boxes.length, 1)), 450);
            });
        } else {
            element.querySelectorAll('[data-count]').forEach(count);
            element.querySelectorAll('.ripeness-fill').forEach((bar, index) => {
                animate(bar, [{transform: 'scaleX(0)'}, {transform: 'scaleX(1)'}], index * 120, 1000);
            });
        }
    }
    if (motion.matches) return;
    const targets = document.querySelectorAll('.result-figure, .result-count-card');
    if ('IntersectionObserver' in window) {
        observer = new IntersectionObserver(entries => entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            observer.unobserve(entry.target);
            reveal(entry.target);
        }), {threshold: 0.08});
        targets.forEach(target => observer.observe(target));
    } else targets.forEach(reveal);
    window.addEventListener('beforeprint', finish);
    window.addEventListener('pagehide', finish);
    motion.addEventListener('change', event => { if (event.matches) finish(); });
})();
