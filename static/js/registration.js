(() => {
 const card = document.querySelector('.registration-card');
 const complete = card.dataset.complete === 'true';
 const form = document.getElementById('registration-form');
 const steps = [...document.querySelectorAll('[data-step]')];
 const progress = [...document.querySelectorAll('[data-progress]')];
 let active = 0;
 if (window.self !== window.top) document.body.classList.add('registration-embedded');
 function show(index, focus = true) {
  active = index;
  steps.forEach((step, i) => { step.hidden = i !== index; });
  progress.forEach((item, i) => {
   item.classList.toggle('is-current', !complete && i === index);
   item.classList.toggle('is-done', complete || i < index);
   if (!complete && i === index) item.setAttribute('aria-current', 'step'); else item.removeAttribute('aria-current');
   item.querySelector('span').textContent = complete || i < index ? '\u2713' : String(i + 1);
  });
  if (index === 2 && form) {
   document.getElementById('review-name').textContent = `${form.elements.first_name.value.trim()} ${form.elements.last_name.value.trim()}`;
   document.getElementById('review-username').textContent = form.elements.username.value.trim();
  }
  if (focus) steps[index]?.querySelector('h1').focus();
 }
 function close(event) {
  if (window.self !== window.top) { event.preventDefault(); window.parent.postMessage({type:'close-auth'}, location.origin); }
 }
 document.querySelector('.registration-close').addEventListener('click', close);
 document.addEventListener('keydown', event => { if (event.key === 'Escape') close(event); });
 document.querySelectorAll('[data-password]').forEach(button => button.addEventListener('click', () => {
  const input = document.getElementById(button.dataset.password), reveal = input.type === 'password';
  input.type = reveal ? 'text' : 'password';
  button.setAttribute('aria-label', reveal ? 'Hide password' : 'Show password');
  button.setAttribute('aria-pressed', String(reveal));
  button.querySelector('span').textContent = reveal ? 'visibility_off' : 'visibility';
 }));
 if (form) {
  form.noValidate = true;
  function matchPasswords() {
   const password = form.elements.password1;
   const invalidLength = password.value.length > 0 && (password.value.length < 8 || password.value.length > 16);
   document.getElementById('registration-password-error').hidden = !invalidLength;
   password.setCustomValidity(invalidLength ? 'Password must be 8–16 characters.' : '');
   password.setAttribute('aria-invalid', String(invalidLength));
   form.elements.password2.setCustomValidity(form.elements.password2.value !== password.value ? 'Passwords do not match.' : '');
  }
  form.elements.password1.addEventListener('input', matchPasswords);
  form.elements.password2.addEventListener('input', matchPasswords);
  function validate(index) {
   matchPasswords();
   for (const input of steps[index].querySelectorAll('input')) {
    if (input.type !== 'password') input.value = input.value.trim();
    if (!input.checkValidity()) { show(index, false); input.reportValidity(); return false; }
   }
   return true;
  }
  document.querySelectorAll('[data-next]').forEach(button => button.addEventListener('click', () => { if (validate(active)) show(active + 1); }));
  document.querySelectorAll('[data-back]').forEach(button => button.addEventListener('click', () => show(active - 1)));
  document.querySelectorAll('[data-edit]').forEach(button => button.addEventListener('click', () => show(Number(button.dataset.edit))));
  form.addEventListener('submit', event => {
   if (active < 2) { event.preventDefault(); if (validate(active)) show(active + 1); return; }
   if (!validate(0) || !validate(1)) { event.preventDefault(); return; }
   const submit = form.querySelector('[type="submit"]'); submit.disabled = true; submit.textContent = 'Creating account…';
  });
  const hasNames = form.elements.first_name.value && form.elements.last_name.value;
  show(document.querySelector('.registration-errors') && hasNames ? 1 : 0, false);
 } else show(2, false);
})();
