(() => {
 const dialog=document.getElementById('fruit-inspector'), fruits=[], groups=[];
 const labels={unripe:'Unripe',ripe:'Ripe',overripe:'Overripe'};
 let active=0, filter='all', busy=false;
 document.querySelectorAll('.result-figure[data-image-id]').forEach((figure,imageIndex)=>{
  const data=figure.querySelectorAll('script[type="application/json"]');
  const group={figure, image:figure.querySelector('img'), boxes:JSON.parse(data[0].textContent), corrections:JSON.parse(data[1].textContent), number:imageIndex+1};
  group.summary=document.createElement('p'); group.summary.className='reviewed-breakdown'; group.summary.setAttribute('aria-live','polite'); figure.append(group.summary); groups.push(group);
  figure.querySelectorAll('[data-fruit-index]').forEach(button=>{
   const index=Number(button.dataset.fruitIndex), fruit={group,index,button,box:group.boxes[index]};
   button.addEventListener('click',()=>{active=fruits.indexOf(fruit);show();dialog.showModal();});fruits.push(fruit);
  });
 });
 function current(f){return f.group.corrections[String(f.index)] || f.box.css_class;}
 function refresh(){
  let matches=0;
  fruits.forEach(f=>{const key=current(f), match=filter==='all'||key===filter;matches+=Number(match); f.button.classList.toggle('fruit-dimmed',!match); f.button.classList.toggle('fruit-highlighted',match&&filter!=='all');f.button.classList.remove('bbox-unripe','bbox-ripe','bbox-overripe');f.button.classList.add('bbox-'+key);f.button.setAttribute('aria-label',`Inspect fruit ${f.index+1}: ${labels[key]||key}`); f.button.querySelector('span').textContent=f.group.corrections[String(f.index)] ? `${labels[key]} (reviewed)` : f.box.label||labels[key];});
  groups.forEach(g=>{const counts={unripe:0,ripe:0,overripe:0};g.boxes.forEach((b,i)=>{const k=g.corrections[String(i)]||b.css_class;if(k in counts) counts[k]++;});g.summary.textContent=`Reviewed breakdown | Image ${g.number} | ${g.boxes.length} detections: `+Object.keys(counts).map(k=>`${labels[k]} ${counts[k]} (${g.boxes.length?(counts[k]/g.boxes.length*100).toFixed(1):'0'}%)`).join(' | ')+'. Original scan summary and grade below are unchanged.';});
  document.getElementById('fruit-filter-status').textContent=fruits.length?`${matches} of ${fruits.length} fruits highlighted across all images.`:'No per-fruit detections are available for this scan.';
 }
 function show(){
  const f=fruits[active];if(!f)return;
  document.getElementById('fruit-number').textContent='Fruit ' + (f.index+1);
  document.getElementById('inspector-position').textContent=`Image ${f.group.number} | Fruit ${f.index+1} | ${active+1} of ${fruits.length}`;
  document.getElementById('inspector-original').textContent='Original estimate: '+(f.box.label||labels[f.box.css_class]||'Unknown')+( /\d/.test(f.box.label||'')?'':' | Score unavailable');
  document.getElementById('fruit-label').value=current(f);
  document.getElementById('inspector-status').textContent='';
  document.getElementById('fruit-prev').disabled=active===0;document.getElementById('fruit-next').disabled=active===fruits.length-1;
  const canvas=document.getElementById('fruit-zoom'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
  function draw(){if(f!==fruits[active])return;const image=f.group.image,b=f.box,w=image.naturalWidth,h=image.naturalHeight;const x=Math.max(0,Number(b.x)/100*w),y=Math.max(0,Number(b.y)/100*h),sw=Math.min(w-x,Number(b.width)/100*w),sh=Math.min(h-y,Number(b.height)/100*h);if(!(sw>0&&sh>0))return;const scale=Math.min(480/sw,360/sh);ctx.drawImage(image,x,y,sw,sh,(480-sw*scale)/2,(360-sh*scale)/2,sw*scale,sh*scale);}
  if(f.group.image.complete)draw();else f.group.image.addEventListener('load',draw,{once:true});
 }
 async function save(label){
  if(busy)return;busy=true;const f=fruits[active];const controls=[...dialog.querySelectorAll('button,select')];controls.forEach(b=>b.disabled=true);
  try{const body=new URLSearchParams({image_id:f.group.figure.dataset.imageId,index:f.index,label});const response=await fetch(location.pathname,{method:'POST',headers:{'X-CSRFToken':dialog.querySelector('[name=csrfmiddlewaretoken]').value},body});if(!response.ok)throw Error();const data=await response.json();f.group.corrections=data.corrections;refresh();show();document.getElementById('inspector-status').textContent='Saved. Reviewed breakdown updated; original analysis preserved.';}catch(_){document.getElementById('inspector-status').textContent='Could not save. Please try again. Your original result is unchanged.';}finally{busy=false;controls.forEach(b=>b.disabled=false);document.getElementById('fruit-prev').disabled=active===0;document.getElementById('fruit-next').disabled=active===fruits.length-1;}
 }
 document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));refresh();}));
 document.getElementById('inspector-close').onclick=()=>dialog.close();dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
 document.getElementById('fruit-prev').onclick=()=>{if(active>0){active--;show();}};document.getElementById('fruit-next').onclick=()=>{if(active<fruits.length-1){active++;show();}};
 document.getElementById('fruit-save').onclick=()=>save(document.getElementById('fruit-label').value);document.getElementById('fruit-reset').onclick=()=>save('original');refresh();
})();

