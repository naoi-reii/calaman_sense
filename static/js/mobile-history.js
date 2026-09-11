(() => {
 const mobile=matchMedia('(max-width: 760px)'), list=document.querySelector('.mobile-history-list');
 const form=document.getElementById('mobile-delete-form'), items=[...list.querySelectorAll('.mobile-history-item')];
 const start=document.getElementById('mobile-selection-start'), cancel=document.getElementById('mobile-selection-cancel'), remove=document.getElementById('mobile-selection-delete');
 let selecting=false,timer=null,submitted=false;
 const boxes=items.map(item=>item.querySelector('input'));
 function update(){const count=boxes.filter(box=>box.checked).length;document.getElementById('mobile-selection-count').textContent=`${count} selected`;remove.disabled=!count;items.forEach((item,i)=>item.classList.toggle('is-selected',boxes[i].checked));}
 function mode(enabled){selecting=enabled;list.classList.toggle('is-selecting',enabled);start.hidden=enabled;cancel.hidden=remove.hidden=!enabled;if(!enabled)boxes.forEach(box=>box.checked=false);update();}
 function stop(){clearTimeout(timer);timer=null;}
 items.forEach(item=>{
  const card=item.querySelector('a'), box=item.querySelector('input');let x=0,y=0;
  card.addEventListener('pointerdown',event=>{if(!mobile.matches||event.button!==0)return;stop();x=event.clientX;y=event.clientY;timer=setTimeout(()=>{mode(true);box.checked=true;item.dataset.justHeld='1';update();timer=null;},550);});
  card.addEventListener('pointermove',event=>{if(Math.hypot(event.clientX-x,event.clientY-y)>10)stop();});
  ['pointerup','pointercancel','pointerleave'].forEach(name=>card.addEventListener(name,stop));
  card.addEventListener('contextmenu',event=>{if(mobile.matches)event.preventDefault();});
  card.addEventListener('click',event=>{if(!mobile.matches||!selecting)return;event.preventDefault();if(box.checked&&item.dataset.justHeld==='1'){delete item.dataset.justHeld;return;}box.checked=!box.checked;update();});
  // Suppress the synthetic click following a successful long press.
  card.addEventListener('pointerdown',()=>{delete item.dataset.justHeld;});

  box.addEventListener('change',update);
 });
 start.disabled=!items.length;start.onclick=()=>mode(true);cancel.onclick=()=>{stop();mode(false);};
 window.addEventListener('scroll',stop,{passive:true,capture:true});
 mobile.addEventListener('change',()=>{stop();mode(false);});
 form.addEventListener('submit',event=>{const count=boxes.filter(b=>b.checked).length;if(!mobile.matches||!count||submitted||!confirm(`Do you want to delete ${count===1?'this scan':`these ${count} scans`}? The saved results and images will be permanently deleted. This cannot be undone.`)){event.preventDefault();return;}submitted=true;remove.disabled=true;remove.textContent='Deleting...';});
 mode(false);
})();

