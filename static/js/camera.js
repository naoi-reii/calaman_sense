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
// Lightweight positioning hint, not a species classifier. Reject small specks,
// clipped subjects and large uniform green backgrounds before auto-capture.
function measureCameraPosition(data, width, height, frame, previous, sourceAspect = 1) {
    const mask = new Uint8Array(width * height);
    let motion = 0, changed = 0, colored = 0;
    for (let i = 0; i < mask.length; i++) {
        const r = data[i*4], g = data[i*4+1], b = data[i*4+2];
        const hi = Math.max(r,g,b), lo = Math.min(r,g,b);
        mask[i] = hi > 45 && hi-lo > 30 && g > b*1.25 && r > b*1.1 && g > r*.65 ? 1 : 0;
        if (previous) {
            motion += Math.abs(r-previous[i*4]) + Math.abs(g-previous[i*4+1]) + Math.abs(b-previous[i*4+2]);
            const pr = previous[i*4], pg = previous[i*4+1], pb = previous[i*4+2];
            const wasColored = Math.max(pr,pg,pb) > 45 && Math.max(pr,pg,pb)-Math.min(pr,pg,pb) > 30 && pg > pb*1.25 && pr > pb*1.1 && pg > pr*.65;
            if (mask[i] || wasColored) colored++;
            if (!!mask[i] !== wasColored) changed++;
        }
    }
    let fruits = 0, outside = false;
    for (let i = 0; i < mask.length; i++) {
        if (!mask[i]) continue;
        const queue = [i]; mask[i] = 0;
        let left = width, right = 0, top = height, bottom = 0;
        for (let j = 0; j < queue.length; j++) {
            const p = queue[j], x = p%width, y = Math.floor(p/width);
            left = Math.min(left,x); right = Math.max(right,x);
            top = Math.min(top,y); bottom = Math.max(bottom,y);
            for (const n of [x > 0 ? p-1 : -1, x < width-1 ? p+1 : -1, y > 0 ? p-width : -1, y < height-1 ? p+width : -1]) {
                if (n >= 0 && mask[n]) { mask[n] = 0; queue.push(n); }
            }
        }
        if (queue.length < width*height*.008) continue;
        const w = right-left+1, h = bottom-top+1;
        if (left < frame.left+2 || right > frame.right-2 || top < frame.top+2 || bottom > frame.bottom-2) outside = true;
        const fill = queue.length/(w*h);
        const aspect = w/h*sourceAspect;
        if (aspect > .55 && aspect < 1.8 && fill > .45 && fill < .93 && queue.length < width*height*.5) fruits++;
    }
    return {positioned: fruits > 0 && !outside, steady: !!previous && motion/(width*height*3) < 7 && changed/Math.max(1,colored) < .12};
}
(() => {
    const dialog = document.getElementById('cameraModal');
    const video = document.getElementById('camera-stream');
    const capture = document.getElementById('capture-btn');
    const flash = document.getElementById('camera-flash');
    const switchButton = document.getElementById('switch-camera-btn');
    const status = document.getElementById('camera-quality');
    const canvas = document.getElementById('camera-canvas');
    const zoomControl = document.getElementById('camera-zoom');
    const viewfinder = dialog.querySelector('.camera-viewfinder');
    let zoomLevel = 1;
    function setZoom(value) {
        if (!stream || capturing) return;
        zoomLevel = Math.max(1, Math.min(4, value));
        zoomControl.value = String(zoomLevel);
        document.getElementById('camera-zoom-value').textContent = zoomLevel.toFixed(1)+'×';
        video.style.transform = `scale(${zoomLevel})`;
        resetReady(); previousFrame = null; quality = null;
    }
    zoomControl.addEventListener('input', () => setZoom(Number(zoomControl.value)));
    document.getElementById('camera-zoom-reset').addEventListener('click', () => setZoom(1));
    const pointers = new Map(); let pinch = null;
    function distance() { const [a,b] = [...pointers.values()]; return Math.hypot(a.x-b.x,a.y-b.y); }
    viewfinder.addEventListener('pointerdown', e => {
        if (e.pointerType !== 'touch' || !stream || capturing) return;
        pointers.set(e.pointerId,{x:e.clientX,y:e.clientY}); viewfinder.setPointerCapture(e.pointerId);
        if (pointers.size === 2) pinch = {distance:distance(),zoom:zoomLevel};
    });
    viewfinder.addEventListener('pointermove', e => {
        if (!pointers.has(e.pointerId)) return;
        pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
        if (pointers.size === 2 && pinch?.distance > 0) setZoom(pinch.zoom*distance()/pinch.distance);
    });
    ['pointerup','pointercancel','lostpointercapture'].forEach(name => viewfinder.addEventListener(name,e => { pointers.delete(e.pointerId); pinch=null; }));
    function crop() {
        const aspect = viewfinder.clientWidth/viewfinder.clientHeight;
        const w = video.videoWidth, h = video.videoHeight;
        const sw = Math.min(w,h*aspect)/zoomLevel, sh = Math.min(h,w/aspect)/zoomLevel;
        return [(w-sw)/2,(h-sh)/2,sw,sh];
    }
    const sample = document.createElement('canvas');
    sample.width = sample.height = 160;
    const sampleContext = sample.getContext('2d', {willReadFrequently: true});
    let stream = null, interval = null, version = 0, facing = 'environment', torch = false;
    let quality = null, previousFocus = null;
    let previousFrame = null, readySince = null, capturing = false, autoFailed = false;
    const frame = dialog.querySelector('.camera-frame');
    function resetReady() {
        readySince = null;
        frame.classList.remove('is-ready');
    }
    function message(text, warning = false) {
        if (status.textContent !== text) status.textContent = text;
        status.classList.toggle('is-warning', warning);
    }
    function release() {
        clearInterval(interval);
        interval = null;
        pointers.clear(); pinch=null; zoomLevel=1; zoomControl.value='1'; zoomControl.disabled=true;
        video.style.transform=''; document.getElementById('camera-zoom-value').textContent='1.0×';
        resetReady();
        previousFrame = null;
        capturing = false;
        autoFailed = false;
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
        if (capturing) return;
        if (!video.videoWidth || video.readyState < 2 || document.hidden) { resetReady(); previousFrame = null; return; }
        // Analyze the same crop that is visible and saved.
        const rect = viewfinder.getBoundingClientRect(), guide = frame.getBoundingClientRect();
        if (!rect.width || !rect.height) { resetReady(); return; }
        const bounds = {left:(guide.left-rect.left)/rect.width*160,right:(guide.right-rect.left)/rect.width*160,top:(guide.top-rect.top)/rect.height*160,bottom:(guide.bottom-rect.top)/rect.height*160};
        const source = crop();
        sampleContext.drawImage(video,...source,0,0,160,160);
        const pixels = sampleContext.getImageData(0,0,160,160).data;
        const position = measureCameraPosition(pixels,160,160,bounds,previousFrame,source[2]/source[3]);
        previousFrame = pixels;
        const score = measureCameraQuality(pixels,160,160);
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
        if (autoFailed) { resetReady(); message('Auto-capture paused. Tap capture to try again.', true); return; }
        if (score.brightness < 55 || score.sharpness < 65) { resetReady(); return; }
        if (score.brightness > 235) { resetReady(); message('Too bright. Avoid glare or direct light.', true); return; }
        if (!position.positioned) {
            resetReady(); message('Place the whole fruit inside the frame for auto-capture.'); return;
        }
        if (!position.steady) { resetReady(); message('Hold steady for auto-capture.'); return; }
        if (readySince === null) readySince = performance.now();
        frame.classList.add('is-ready');
        const remaining = 1800-(performance.now()-readySince);
        message('Hold steady. Auto-capture in ' + Math.max(1,Math.ceil(remaining/1000)) + '...');
        if (remaining <= 0) takePhoto();
    }
    async function start() {
        const token = ++version;
        release();
        switchButton.disabled = true;
        message('Starting camera...');
        try {
            if (!navigator.mediaDevices?.getUserMedia) throw new Error('unsupported');
            let result = await navigator.mediaDevices.getUserMedia({audio:false, video:{facingMode:{ideal:facing}, width:{ideal:1920},height:{ideal:1080}}});
            if (token !== version || dialog.hidden) { result.getTracks().forEach(track => track.stop()); return; }
            // Prefer a normal rear lens when the browser exposes lens labels.
            if (facing === 'environment' && navigator.mediaDevices.enumerateDevices) {
                try {
                    const devices = await navigator.mediaDevices.enumerateDevices();
                    const rear = devices.filter(d => d.kind==='videoinput' && /back|rear|environment/i.test(d.label) && !/ultra|0[.,]5|telephoto|depth|macro/i.test(d.label));
                    const normal = rear.find(d => /main|standard|back camera$|rear camera$/i.test(d.label)) || rear[0];
                    if (token !== version || dialog.hidden) { result.getTracks().forEach(t=>t.stop()); return; }
                    if (normal && normal.deviceId !== result.getVideoTracks()[0].getSettings().deviceId) {
                        result.getTracks().forEach(t=>t.stop());
                        result = await navigator.mediaDevices.getUserMedia({audio:false,video:{deviceId:{exact:normal.deviceId},width:{ideal:1920},height:{ideal:1080}}});
                    }
                } catch (_) {
                    if (result.getVideoTracks()[0].readyState === 'ended') result = await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:facing}}});
                }
            }
            if (token !== version || dialog.hidden) { result.getTracks().forEach(t=>t.stop()); return; }
            stream = result;
            video.srcObject = stream;
            await video.play();
            if (token !== version) return;
            const track = stream.getVideoTracks()[0];
            const capabilities = track.getCapabilities?.() || {};
            if (capabilities.zoom) {
                try { await track.applyConstraints({advanced:[{zoom:Math.max(capabilities.zoom.min,Math.min(capabilities.zoom.max,1))}]}); } catch (_) {}
            }
            if (token !== version) return;
            zoomControl.disabled = false;
            flash.disabled = !capabilities.torch;
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
    function takePhoto() {
        if (!stream || !video.videoWidth || capture.disabled || capturing) return;
        capturing = true;
        resetReady();
        message('Capturing photo...');
        capture.disabled = true;
        clearInterval(interval);
        const token = version;
        const source = crop();
        canvas.width = Math.max(1,Math.round(source[2]));
        canvas.height = Math.max(1,Math.round(source[3]));
        canvas.getContext('2d').drawImage(video,...source,0,0,canvas.width,canvas.height);
        canvas.toBlob(blob => {
            if (token !== version) return;
            capturing = false;
            if (!blob) { autoFailed=true; message('Could not capture. Please try again.',true); capture.disabled=false; interval=setInterval(checkQuality,600); return; }
            const photo = new File([blob], 'capture_' + Date.now() + '.jpg', {type:'image/jpeg'});
            if (selectImages([...fileInput.files,photo])) close();
            else { autoFailed=true; message('Photo could not be added. Check the selected photos or try Gallery.',true); capture.disabled=false; interval=setInterval(checkQuality,600); }
        },'image/jpeg',.92);
    }
    capture.addEventListener('click', takePhoto);
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

