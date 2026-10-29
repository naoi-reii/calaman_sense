let activePreview = 0;
let previewUrls = [];
const previewControls = document.getElementById('preview-controls');
const previewPrevious = document.getElementById('preview-prev');
const previewNext = document.getElementById('preview-next');

function updatePreviewPosition() {
    const count = fileInput.files.length;
    document.getElementById('preview-position').textContent = count ? `${activePreview + 1} of ${count}` : '';
    previewPrevious.disabled = activePreview === 0;
    previewNext.disabled = activePreview >= count - 1;
}

function movePreview(index) {
    activePreview = Math.max(0, Math.min(fileInput.files.length - 1, index));
    const slide = previewContainer.children[activePreview];
    if (slide) previewContainer.scrollTo({left: slide.offsetLeft - previewContainer.offsetLeft, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    updatePreviewPosition();
}

function renderPreviews() {
    const files = Array.from(fileInput.files);
    previewUrls.forEach(url => URL.revokeObjectURL(url));
    previewUrls = [];
    previewContainer.replaceChildren();
    activePreview = Math.max(0, Math.min(activePreview, files.length - 1));
    document.getElementById('submit-btn').disabled = !files.length;
    document.getElementById('selected-count').textContent = uploadForm.dataset.selectedLabel.replace('{count}', files.length);
    document.getElementById('clear-selected').hidden=!files.length;
    document.querySelector('#submit-btn .desktop-source-label').textContent = uploadForm.dataset.analyzeLabel + (files.length ? ` (${files.length})` : '');
    document.getElementById('selection-empty').hidden = !!files.length;
    dropzone.classList.toggle('has-images', !!files.length);
    previewContainer.style.display = files.length ? 'flex' : 'none';
    previewControls.hidden = files.length < 2;
    document.getElementById('preview-help').hidden = files.length < 2;

    files.forEach((file, index) => {
        const slide = document.createElement('div');
        slide.className = 'preview-slide';
        slide.setAttribute('role', 'group');
        slide.setAttribute('aria-label', `Photo ${index + 1} of ${files.length}`);
        const image = document.createElement('img');
        const url = URL.createObjectURL(file);
        previewUrls.push(url);
        image.src = url;
        image.alt = file.name;
        image.className = 'preview-thumb';
        image.draggable = false;
        const name = document.createElement('p');
        name.className = 'preview-filename';
        name.textContent = file.name;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'preview-remove';
        remove.textContent = '×';
        remove.setAttribute('aria-label', `Remove ${file.name}`);
        remove.addEventListener('click', () => {
            const remaining = Array.from(fileInput.files);
            remaining.splice(index, 1);
            activePreview = index;
            selectImages(remaining);
            previewContainer.focus({preventScroll: true});
        });
        slide.append(image, remove, name);
        previewContainer.append(slide);
    });
    updatePreviewPosition();
    // Keep the current position when adding or removing photos.
    const slide = previewContainer.children[activePreview];
    previewContainer.scrollLeft = slide ? slide.offsetLeft - previewContainer.offsetLeft : 0;
}

previewPrevious.addEventListener('click', () => movePreview(activePreview - 1));
previewNext.addEventListener('click', () => movePreview(activePreview + 1));
previewContainer.addEventListener('keydown', event => {
    if (event.target !== previewContainer || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    movePreview(activePreview + (event.key === 'ArrowRight' ? 1 : -1));
});
previewContainer.addEventListener('scroll', () => {
    if (!previewContainer.clientWidth || !fileInput.files.length) return;
    activePreview = Math.max(0, Math.min(fileInput.files.length - 1, Math.round(previewContainer.scrollLeft / previewContainer.clientWidth)));
    updatePreviewPosition();
});
window.addEventListener('resize', () => {
    const slide = previewContainer.children[activePreview];
    if (slide) previewContainer.scrollLeft = slide.offsetLeft - previewContainer.offsetLeft;
});
window.addEventListener('pagehide', () => previewUrls.forEach(url => URL.revokeObjectURL(url)));
renderPreviews();

 document.getElementById('clear-selected').addEventListener('click',()=>{selectImages([]);previewContainer.focus();});
