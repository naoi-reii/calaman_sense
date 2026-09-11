/* Quality scores are advisory heuristics on a small central image, not a fruit detector. */
function measureCameraQuality(data, width, height) {
    const gray = new Float32Array(width * height);
    let brightness = 0;
    for (let i = 0; i < gray.length; i++) {
        gray[i] = .299 * data[i * 4] + .587 * data[i * 4 + 1] + .114 * data[i * 4 + 2];
        brightness += gray[i];
    }
    let sum = 0, squared = 0, count = 0;
    for (let y = 1; y < height - 1; y++) for (let x = 1; x < width - 1; x++) {
        const i = y * width + x;
        const edge = gray[i - 1] + gray[i + 1] + gray[i - width] + gray[i + width] - 4 * gray[i];
        sum += edge; squared += edge * edge; count++;
    }
    return { brightness: brightness / gray.length, sharpness: squared / count - (sum / count) ** 2 };
}
(() => {
    const dialog = document.getElementById('cameraModal');
    const video = document.getElementById('camera-stream');
    const capture = document.getElementById('capture-btn');
    const flash = document.getElementById('camera-flash');
    const switchButton = document.getElementById('switch-camera-btn');
    const status = document.getElementById('camera-quality');
    const canvas = document.getElementById('camera-canvas');
    const sample = document.createElement('canvas');
    sample.width = sample.height = 160;
    const sampleContext = sample.getContext('2d', {willReadFrequently: true});
    let stream = null, interval = null, version = 0, facing = 'environment', torch = false;
    let quality = null, previousFocus = null;
    function message(text, warning = false) {
        if (status.textContent !== text) status.textContent = text;
        status.classList.toggle('is-warning', warning);
    }
    function release() {
        clearInterval(interval);
        interval = null;
        if (stream) stream.getTracks().forEach(track => track.stop());
        stream = null;
        video.srcObject = null;
        capture.disabled = true;
        flash.disabled = true;
        torch = false;
        flash.setAttribute('aria-pressed', 'false');
        flash.querySelector('.material-symbols-outlined').textContent = 'flash_off';
        document.getElementById('flash-label').textContent = 'Flash unavailable';
        quality = null;
    }
    function close() {
        version++;
        release();
        dialog.hidden = true;
        document.body.classList.remove('camera-open', 'desktop-camera-active');
        document.getElementById('open-camera-btn').classList.remove('scan-source-active');
        document.getElementById('browse-images-btn').classList.add('scan-source-active');
        document.querySelector('main').inert = false;
        document.querySelectorAll('.overview-topbar,.overview-sidebar,.mobile-bottom-nav').forEach(el => el.inert = false);
        if (previousFocus) previousFocus.focus({preventScroll: true});
    }
    function checkQuality() {
        if (!video.videoWidth || video.readyState < 2) return;
        const side = Math.min(video.videoWidth, video.videoHeight) * .8;
        sampleContext.drawImage(video, (video.videoWidth-side)/2, (video.videoHeight-side)/2, side, side, 0, 0, 160, 160);
        const score = measureCameraQuality(sampleContext.getImageData(0,0,160,160).data,160,160);
        quality = quality ? {brightness: quality.brightness*.65+score.brightness*.35, sharpness: quality.sharpness*.65+score.sharpness*.35} : score;
        if (quality.brightness < 55) {
            message('Too dark (madilim). Move to better light or turn on flash.', true);
            capture.disabled = true;
        } else if (quality.sharpness < 65) {
            message('Looks blurry. Hold steady, clean the lens, or adjust the distance.', true);
            capture.disabled = false;
        } else {
            message('Lighting and sharpness look good. Ready to capture.');
            capture.disabled = false;
        }
    }
    async function start() {
        const token = ++version;
        release();
        switchButton.disabled = true;
        message('Starting camera...');
        try {
            if (!navigator.mediaDevices?.getUserMedia) throw new Error('unsupported');
            const result = await navigator.mediaDevices.getUserMedia({audio:false, video:{facingMode:{ideal:facing}, width:{ideal:1920},height:{ideal:1080}}});
            if (token !== version || dialog.hidden) { result.getTracks().forEach(track => track.stop()); return; }
            stream = result;
            video.srcObject = stream;
            await video.play();
            if (token !== version) return;
            const track = stream.getVideoTracks()[0];
            flash.disabled = !track.getCapabilities?.().torch;
            document.getElementById('flash-label').textContent = flash.disabled ? 'Flash unavailable' : 'Flash';
            track.addEventListener('ended', () => { if (token === version) { release(); message('Camera disconnected. Close and reopen the camera.',true); } });
            interval = setInterval(checkQuality, 600);
            checkQuality();
        } catch (error) {
            if (token !== version) return;
            release();
            message(error.name === 'NotAllowedError' ? 'Camera permission denied. Allow camera access or choose Gallery.' : 'Camera unavailable. Use HTTPS or localhost, check camera access, or choose Gallery.',true);
        } finally { if (token === version) switchButton.disabled = false; }
    }
    function open() {
        previousFocus = document.activeElement;
        if (window.matchMedia('(min-width: 761px)').matches) {
            document.getElementById('desktop-camera-slot').appendChild(dialog);
            dialog.hidden = false;
            dialog.setAttribute('role', 'region');
            dialog.removeAttribute('aria-modal');
            document.body.classList.add('desktop-camera-active');
            document.getElementById('open-camera-btn').classList.add('scan-source-active');
            document.getElementById('browse-images-btn').classList.remove('scan-source-active');
            start();
            return;
        }
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        // Move the dialog out of main before making the background inert.
        document.body.appendChild(dialog);
        dialog.hidden = false;
        document.body.classList.add('camera-open');
        document.querySelector('main').inert = true;
        document.querySelectorAll('.overview-topbar,.overview-sidebar,.mobile-bottom-nav').forEach(el => el.inert = true);
        document.getElementById('close-camera-btn').focus();
        start();
    }
    document.getElementById('open-camera-btn').addEventListener('click',open);
    document.getElementById('browse-images-btn').addEventListener('click', () => { if (!dialog.hidden) close(); });
    window.matchMedia('(min-width: 761px)').addEventListener('change', () => { if (!dialog.hidden) close(); });
    document.getElementById('close-camera-btn').addEventListener('click',close);
    switchButton.addEventListener('click', () => { facing = facing === 'environment' ? 'user' : 'environment'; start(); });
    document.getElementById('camera-gallery').addEventListener('click', () => { close(); fileInput.click(); });
    flash.addEventListener('click', async () => {
        const track = stream?.getVideoTracks()[0];
        if (!track) return;
        flash.disabled = true;
        try {
            await track.applyConstraints({advanced:[{torch:!torch}]});
            torch = !torch;
            flash.setAttribute('aria-pressed',String(torch));
            flash.querySelector('.material-symbols-outlined').textContent = torch ? 'flash_on' : 'flash_off';
            document.getElementById('flash-label').textContent = torch ? 'Flash on' : 'Flash';
        } catch (_) { message('Flash could not be changed. Try moving to better light.',true); }
        finally { if (stream?.getVideoTracks()[0] === track) flash.disabled = false; }
    });
    capture.addEventListener('click', () => {
        if (!stream || !video.videoWidth || capture.disabled) return;
        capture.disabled = true;
        clearInterval(interval);
        const token = version;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
        canvas.toBlob(blob => {
            if (token !== version) return;
            if (!blob) { message('Could not capture. Please try again.',true); capture.disabled=false; interval=setInterval(checkQuality,600); return; }
            const photo = new File([blob], 'capture_' + Date.now() + '.jpg', {type:'image/jpeg'});
            if (selectImages([...fileInput.files,photo])) close();
            else { message('Photo exceeds 10MB. Try Gallery with a smaller image.',true); capture.disabled=false; interval=setInterval(checkQuality,600); }
        },'image/jpeg',.92);
    });
    document.addEventListener('keydown', event => {
        if (dialog.hidden) return;
        if (event.key === 'Escape') close();
        if (event.key === 'Tab' && dialog.getAttribute('role') === 'dialog') {
            const buttons = [...dialog.querySelectorAll('button:not(:disabled)')];
            const first = buttons[0], last = buttons[buttons.length-1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
    });
    window.addEventListener('pagehide',close);
    document.addEventListener('visibilitychange', () => { if (document.hidden && !dialog.hidden) close(); });
    if (location.hash === '#open-camera-btn') open();
})();

