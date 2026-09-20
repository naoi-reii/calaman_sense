(() => {
    const form = document.getElementById('profile-edit-form');
    const summary = document.getElementById('profile-summary');
    const edit = document.getElementById('edit-profile');
    const cancel = document.getElementById('cancel-edit');
    const photoForm = document.getElementById('profile-photo-form');
    const photoButton = document.getElementById('change-photo');
    const avatar = document.getElementById('open-photo-editor');
    const input = document.getElementById('id_photo');
    const dialog = document.getElementById('profile-photo-dialog');
    const preview = document.getElementById('photo-dialog-preview');
    const initial = document.getElementById('photo-dialog-initial');
    const original = document.getElementById('profile-photo-preview').getAttribute('src');
    const status = document.getElementById('photo-status');
    const cameraInput = document.getElementById('photo-camera-input');
    const panel = document.getElementById('profile-camera-panel');
    const video = document.getElementById('profile-camera-video');
    const shutter = document.getElementById('profile-camera-capture');
    const savePhoto = photoForm.querySelector('button[type="submit"]');
    let url = null, stream = null, cameraVersion = 0;
    function showEditor(show) { form.hidden = !show; summary.hidden = show; edit.hidden = show; }
    function stopCamera() {
        cameraVersion++;
        if (stream) stream.getTracks().forEach(track => track.stop());
        stream = null; video.srcObject = null; panel.hidden = true;
    }
    function showPhoto(show) {
        if (show && !dialog.open) dialog.showModal();
        if (!show && dialog.open) dialog.close();
        document.body.classList.toggle('profile-photo-open', show);
        avatar.setAttribute('aria-expanded', String(show));
        photoButton.setAttribute('aria-expanded', String(show));
        if (!show) stopCamera();
    }
    function updatePreview() {
        savePhoto.disabled = !input.files.length;
        if (url) { URL.revokeObjectURL(url); url = null; }
        const file = input.files[0];
        const source = file ? (url = URL.createObjectURL(file)) : original;
        preview.hidden = !source;
        if (source) preview.src = source;
        if (initial) initial.hidden = !!source;
    }
    function selectPhoto(file) {
        if (!file) return;
        if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 5*1024*1024) {
            status.textContent = 'Choose a JPG, PNG or WebP photo smaller than 5MB.';
            input.value = ''; updatePreview(); return;
        }
        const files = new DataTransfer(); files.items.add(file); input.files = files.files;
        updatePreview(); stopCamera();
        status.textContent = 'Photo ready. Tap Save Photo to keep it.';
    }
    cancel.hidden = false; photoButton.hidden = false;
    updatePreview();
    savePhoto.disabled = !input.files.length;
    showEditor(form.dataset.errors === 'true');
    showPhoto(photoForm.dataset.errors === 'true');
    edit.addEventListener('click', () => { showEditor(true); document.getElementById('id_first_name').focus(); });
    cancel.addEventListener('click', () => { form.reset(); showEditor(false); edit.focus(); });
    [photoButton, avatar].forEach(button => button.addEventListener('click', () => { showPhoto(true); document.getElementById('photo-album').focus(); }));
    function cancelPhoto() {
        if (photoForm.querySelector('button[type="submit"]').textContent === 'Saving...') return;
        photoForm.reset(); cameraInput.value = ''; status.textContent = ''; updatePreview(); showPhoto(false); avatar.focus();
    }
    document.getElementById('cancel-photo').addEventListener('click', cancelPhoto);
    document.getElementById('close-photo-dialog').addEventListener('click', cancelPhoto);
    dialog.addEventListener('cancel', event => { event.preventDefault(); cancelPhoto(); });
    dialog.addEventListener('click', event => {
        const rect = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) cancelPhoto();
    });
    document.getElementById('photo-album').addEventListener('click', () => { stopCamera(); input.click(); });
    input.addEventListener('change', () => { if (input.files.length) selectPhoto(input.files[0]); });
    cameraInput.addEventListener('change', () => { selectPhoto(cameraInput.files[0]); cameraInput.value = ''; });
    document.getElementById('photo-camera').addEventListener('click', async () => {
        stopCamera();
        // Mobile devices can open their native front camera directly.
        if (window.matchMedia('(pointer: coarse)').matches) { cameraInput.click(); return; }
        const token = cameraVersion;
        status.textContent = 'Opening camera...'; shutter.disabled = true;
        try {
            if (!navigator.mediaDevices?.getUserMedia) throw new Error('unavailable');
            const result = await navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:'user'}});
            if (token !== cameraVersion) { result.getTracks().forEach(track => track.stop()); return; }
            stream = result; panel.hidden = false; video.srcObject = stream;
            await video.play();
            if (token !== cameraVersion) return;
            shutter.disabled = false; status.textContent = 'Ready. Tap Take Photo.';
        } catch (error) {
            if (token !== cameraVersion) return;
            stopCamera(); status.textContent = 'Camera unavailable. Allow camera access on HTTPS or localhost, or choose Album.';
        }
    });
    shutter.addEventListener('click', () => {
        if (!stream || !video.videoWidth || shutter.disabled) return;
        shutter.disabled = true;
        const token = cameraVersion, canvas = document.createElement('canvas');
        const scale = Math.min(1,1200/Math.max(video.videoWidth,video.videoHeight));
        canvas.width = Math.round(video.videoWidth*scale); canvas.height = Math.round(video.videoHeight*scale);
        canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
        canvas.toBlob(blob => {
            if (token !== cameraVersion) return;
            shutter.disabled = false;
            if (blob) selectPhoto(new File([blob],'profile-camera.jpg',{type:'image/jpeg'}));
            else status.textContent = 'Could not take photo. Please try again.';
        },'image/jpeg',.9);
    });
    document.getElementById('profile-camera-stop').addEventListener('click', stopCamera);
    photoForm.addEventListener('submit', event => {
        if (!input.files.length) { event.preventDefault(); status.textContent = 'Choose Album or Camera first.'; return; }
        stopCamera();
        savePhoto.disabled = true;
        savePhoto.textContent = 'Saving...';
        document.getElementById('cancel-photo').disabled = true;
    });
    form.addEventListener('submit', () => {
        const save = form.querySelector('button[type="submit"]');
        save.disabled = true; save.textContent = 'Saving...'; cancel.disabled = true;
    });
    window.addEventListener('pageshow', () => {
        savePhoto.disabled = !input.files.length; savePhoto.textContent = 'Save Photo';
        document.getElementById('cancel-photo').disabled = false;
        const save = form.querySelector('button[type="submit"]');
        save.disabled = false; save.textContent = 'Save Changes'; cancel.disabled = false;
    });
    document.addEventListener('visibilitychange', () => { if (document.hidden) stopCamera(); });
    window.addEventListener('pagehide', () => { stopCamera(); if (url) URL.revokeObjectURL(url); });
})();
