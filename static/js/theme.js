(() => {
 const root=document.documentElement;
 function apply(dark){root.dataset.theme=dark?'dark':'light';root.style.colorScheme=dark?'dark':'light';sync();}
 function sync(){const dark=root.dataset.theme==='dark';document.querySelectorAll('#darkModeToggle').forEach(input=>input.checked=dark);document.querySelectorAll('[name="appearance"]').forEach(input=>input.checked=input.value===(dark?'dark':'light'));}
 function set(dark){try{localStorage.setItem('darkMode',dark?'enabled':'disabled');}catch(_){}apply(dark);}
 let dark=false;try{dark=localStorage.getItem('darkMode')==='enabled';}catch(_){}apply(dark);
 document.addEventListener('DOMContentLoaded',()=>{sync();document.getElementById('darkModeToggle')?.addEventListener('change',event=>set(event.target.checked));document.querySelectorAll('[name="appearance"]').forEach(input=>input.addEventListener('change',()=>{if(input.checked)set(input.value==='dark');}));});
 window.addEventListener('storage',event=>{if(event.key==='darkMode')apply(event.newValue==='enabled');});
})();
