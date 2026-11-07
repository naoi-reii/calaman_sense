(() => {
    let pending = false, request = null, generation = 0, answer = null;
    const dialog = document.getElementById('cancel-scan-dialog');
    // Keep the modal outside the content hidden by the loading screen.
    document.body.appendChild(dialog);
    const marker = 'scan-' + Date.now();
    let cleaningHistory = null;
    function ask() {
        if (answer) return null;
        return new Promise(resolve => { answer = resolve; dialog.showModal(); });
    }
    function finishDialog(value) {
        const resolve = answer;
        answer = null;
        if (dialog.open) dialog.close();
        resolve?.(value);
    }
    document.getElementById('continue-scan').addEventListener('click', () => finishDialog(false));
    document.getElementById('confirm-cancel-scan').addEventListener('click', () => finishDialog(true));
    dialog.addEventListener('cancel', event => { event.preventDefault(); finishDialog(false); });
    function warnBeforeLeaving(event) {
        if (!pending) return;
        event.preventDefault(); event.returnValue = '';
    }
    function removeHistoryMarker() {
        if (cleaningHistory) return cleaningHistory;
        if (history.state?.scanGuard !== marker) return Promise.resolve();
        cleaningHistory = new Promise(resolve => {
            window.addEventListener('popstate', () => { cleaningHistory = null; resolve(); }, {once:true});
            history.back();
        });
        return cleaningHistory;
    }
    async function restore() {
        pending = false;
        window.removeEventListener('beforeunload', warnBeforeLeaving);
        finishDialog(false);
        await removeHistoryMarker();
        uploadLoading.hidden = true;
        document.body.classList.remove('upload-is-loading');
        delete uploadForm.dataset.submitting;
        uploadForm.removeAttribute('aria-busy');
        document.getElementById('submit-btn').disabled = !fileInput.files.length;
    }
    function abortScan() { generation++; request?.abort(); }
    document.addEventListener('click', async event => {
        if (!pending || dialog.contains(event.target)) return;
        const control = event.target.closest('a, button, input[type=submit]');
        if (!control) return;
        event.preventDefault(); event.stopImmediatePropagation();
        const confirmation = ask();
        if (!confirmation || !await confirmation || !pending) return;
        abortScan();
        await restore();
        control.click();
    }, true);
    window.addEventListener('popstate', async () => {
        if (!pending) return;
        // A temporary history entry lets ordinary browser Back show our own modal.
        const confirmation = ask();
        if (!confirmation) return;
        if (await confirmation && pending) {
            abortScan();
            await restore();
            history.back();
        } else if (pending) {
            history.pushState({scanGuard:marker}, '', location.href);
        }
    });
    uploadForm.addEventListener('submit', async event => {
        event.preventDefault();
        if (pending || cleaningHistory) return;
        const token = ++generation;
        request = new AbortController(); pending = true;
        history.pushState({scanGuard:marker}, '', location.href);
        uploadForm.dataset.submitting = 'true';
        uploadForm.setAttribute('aria-busy', 'true');
        document.getElementById('submit-btn').disabled = true;
        document.body.classList.add('upload-is-loading');
        uploadLoading.hidden = false;
        window.scrollTo(0, 0); uploadLoading.focus();
        window.addEventListener('beforeunload', warnBeforeLeaving);
        try {
            const response = await fetch(uploadForm.action || location.href, {
                method:'POST', body:new FormData(uploadForm), credentials:'same-origin', signal:request.signal,
            });
            if (token !== generation) return;
            if (response.redirected) {
                pending = false;
                window.removeEventListener('beforeunload', warnBeforeLeaving);
                finishDialog(false);
                await removeHistoryMarker();
                window.location.assign(response.url);
                return;
            }
            if (!response.ok) throw new Error('Analysis failed');
            const html = await response.text();
            if (token !== generation) return;
            const result = new DOMParser().parseFromString(html, 'text/html');
            const feedback = result.querySelector('.upload-server-feedback');
            await restore();
            if (feedback) {
                document.querySelector('.upload-server-feedback')?.remove();
                uploadForm.before(document.importNode(feedback, true));
                window.scrollTo(0, 0);
            } else {
                uploadError.textContent = 'Analysis did not finish. Please try again.';
                uploadError.hidden = false;
            }
        } catch (error) {
            if (token !== generation) return;
            await restore();
            if (error.name !== 'AbortError') {
                uploadError.textContent = 'Could not complete the scan. Please try again.';
                uploadError.hidden = false;
            }
        }
    });
    window.addEventListener('pagehide', () => {
        abortScan(); pending = false;
        window.removeEventListener('beforeunload', warnBeforeLeaving);
        finishDialog(false);
    });
})();
