(() => {
 const dialog=document.getElementById('fruit-inspector'), fruits=[], groups=[];
 const labels={unripe:'Unripe',ripe:'Ripe',overripe:'Overripe'};
 const motion=matchMedia('(prefers-reduced-motion: reduce)'), zoom=document.getElementById('fruit-zoom-level');
 let active=0, filter='all', busy=false, opener=null, pictureAnimation=null, drawCurrent=()=>{};
 function animate(element, frames){if(!motion.matches&&element.animate)return element.animate(frames,{duration:330,easing:'cubic-bezier(.22,1,.36,1)'});}
 document.querySelectorAll('.result-figure[data-image-id]').forEach((figure,imageIndex)=>{
  const data=figure.querySelectorAll('script[type="application/json"]');
  const group={figure, image:figure.querySelector('img'), boxes:JSON.parse(data[0].textContent), corrections:JSON.parse(data[1].textContent), number:imageIndex+1};
  group.summary=document.createElement('p'); group.summary.className='reviewed-breakdown'; group.summary.setAttribute('aria-live','polite'); figure.append(group.summary); groups.push(group);
  figure.querySelectorAll('[data-fruit-index]').forEach(button=>{
   const index=Number(button.dataset.fruitIndex), fruit={group,index,button,box:group.boxes[index]};
   button.addEventListener('click',()=>{if(busy)return;opener=button;active=fruits.indexOf(fruit);dialog.showModal();document.body.classList.add('fruit-inspector-open');show();animate(dialog,[{opacity:0,transform:'translateY(22px) scale(.97)'},{opacity:1,transform:'translateY(0) scale(1)'}]);});fruits.push(fruit);
  });
 });
 function current(f){return f.group.corrections[String(f.index)] || f.box.css_class;}
 function refresh(){
  let matches=0;
  fruits.forEach(f=>{const key=current(f), match=filter==='all'||key===filter;matches+=Number(match); f.button.classList.toggle('fruit-dimmed',!match); f.button.classList.toggle('fruit-highlighted',match&&filter!=='all');f.button.classList.remove('bbox-unripe','bbox-ripe','bbox-overripe');f.button.classList.add('bbox-'+key);f.button.setAttribute('aria-label',`Inspect image ${f.group.number}, fruit ${f.index+1}: ${labels[key]||key}`); f.button.querySelector('.bounding-box-label').textContent=f.group.corrections[String(f.index)] ? `${labels[key]} (reviewed)` : f.box.label||labels[key];});
  groups.forEach(g=>{const counts={unripe:0,ripe:0,overripe:0};g.boxes.forEach((b,i)=>{const k=g.corrections[String(i)]||b.css_class;if(k in counts) counts[k]++;});g.summary.textContent=`Reviewed breakdown | Image ${g.number} | ${g.boxes.length} detections: `+Object.keys(counts).map(k=>`${labels[k]} ${counts[k]} (${g.boxes.length?(counts[k]/g.boxes.length*100).toFixed(1):'0'}%)`).join(' | ')+'. Original scan summary and grade below are unchanged.';});
  document.getElementById('fruit-filter-status').textContent=fruits.length?`${matches} of ${fruits.length} fruits highlighted across all images.`:'No per-fruit detections are available for this scan.';
  document.querySelector('.fruit-tap-hint').hidden=!fruits.length;
 }
 function show(){
  const f=fruits[active];if(!f)return;
  zoom.value='1';document.getElementById('fruit-zoom-value').textContent='1.0×';
  document.getElementById('fruit-number').textContent='Fruit ' + (f.index+1);
  document.getElementById('inspector-position').textContent=`Image ${f.group.number} | Fruit ${f.index+1} | ${active+1} of ${fruits.length}`;
  document.getElementById('inspector-original').textContent='Original estimate: '+(f.box.label||labels[f.box.css_class]||'Unknown')+( /\d/.test(f.box.label||'')?'':' | Score unavailable');
  document.getElementById('fruit-label').value=current(f);
  document.getElementById('inspector-status').textContent='';
  document.getElementById('fruit-prev').disabled=active===0;document.getElementById('fruit-next').disabled=active===fruits.length-1;
  const canvas=document.getElementById('fruit-zoom'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
  canvas.setAttribute('aria-label',`Image ${f.group.number}, fruit ${f.index+1}: ${labels[current(f)]||'Unknown'}. Enlarged photo.`);
  function draw(){
   if(f!==fruits[active]||!ctx)return;
   ctx.clearRect(0,0,canvas.width,canvas.height);
   const image=f.group.image,b=f.box,w=image.naturalWidth,h=image.naturalHeight;
   if(!image.complete||!w){ctx.fillStyle='#52675a';ctx.font='20px sans-serif';ctx.textAlign='center';ctx.fillText(image.complete?'Photo unavailable':'Loading photo…',canvas.width/2,canvas.height/2);return;}
   const x=Math.max(0,Number(b.x)/100*w),y=Math.max(0,Number(b.y)/100*h),sw=Math.min(w-x,Number(b.width)/100*w),sh=Math.min(h-y,Number(b.height)/100*h);
   if(!(sw>0&&sh>0))return;
   const scale=Math.min(canvas.width/sw,canvas.height/sh)*Number(zoom.value);
   ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';ctx.drawImage(image,x,y,sw,sh,(canvas.width-sw*scale)/2,(canvas.height-sh*scale)/2,sw*scale,sh*scale);
  }
  drawCurrent=draw;draw();
  pictureAnimation?.cancel();pictureAnimation=animate(canvas,[{opacity:.25,transform:'scale(.95)'},{opacity:1,transform:'scale(1)'}]);
  if(!f.group.image.complete){f.group.image.addEventListener('load',draw,{once:true});f.group.image.addEventListener('error',draw,{once:true});}
 }
 async function save(label){
  if(busy)return;busy=true;const f=fruits[active];const controls=[...dialog.querySelectorAll('button,select,input')];controls.forEach(b=>b.disabled=true);
  document.getElementById('inspector-status').textContent='Saving review…';
  try{const cookie=document.cookie.split(';').map(part=>part.trim()).find(part=>part.startsWith('csrftoken='));const token=cookie?cookie.slice(10):dialog.querySelector('[name=csrfmiddlewaretoken]').value;const body=new URLSearchParams({image_id:f.group.figure.dataset.imageId,index:f.index,label});const response=await fetch(location.pathname,{method:'POST',headers:{'X-CSRFToken':token},body});if(!response.ok)throw Error();const data=await response.json();f.group.corrections=data.corrections;refresh();show();document.getElementById('inspector-status').textContent='Saved. Reviewed breakdown updated; original analysis preserved.';}catch(_){document.getElementById('inspector-status').textContent='Could not save. Please try again. Your original result is unchanged.';}finally{busy=false;controls.forEach(b=>b.disabled=false);document.getElementById('fruit-prev').disabled=active===0;document.getElementById('fruit-next').disabled=active===fruits.length-1;}
 }
 document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));refresh();}));
 document.getElementById('inspector-close').onclick=()=>{if(!busy)dialog.close();};dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
 dialog.addEventListener('close',()=>{pictureAnimation?.cancel();document.body.classList.remove('fruit-inspector-open');opener?.focus({preventScroll:true});});
 function navigate(direction){if(busy||active+direction<0||active+direction>=fruits.length)return;active+=direction;show();}
 document.getElementById('fruit-prev').onclick=()=>navigate(-1);document.getElementById('fruit-next').onclick=()=>navigate(1);
 zoom.addEventListener('input',()=>{document.getElementById('fruit-zoom-value').textContent=Number(zoom.value).toFixed(1)+'×';drawCurrent();});
 dialog.addEventListener('keydown',event=>{if(event.target.closest('input,select,textarea')||!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();navigate(event.key==='ArrowRight'?1:-1);});
 const photo=document.getElementById('fruit-zoom');let gesture=null;
 photo.addEventListener('pointerdown',event=>{if(!event.isPrimary||event.button!==0||busy)return;gesture={x:event.clientX,y:event.clientY,id:event.pointerId};photo.setPointerCapture(event.pointerId);});
 photo.addEventListener('pointerup',event=>{if(!gesture||gesture.id!==event.pointerId)return;const dx=event.clientX-gesture.x,dy=event.clientY-gesture.y;gesture=null;if(Math.abs(dx)>45&&Math.abs(dx)>Math.abs(dy)*1.3)navigate(dx<0?1:-1);});
 photo.addEventListener('pointercancel',()=>{gesture=null;});photo.addEventListener('lostpointercapture',()=>{gesture=null;});
 motion.addEventListener('change',event=>{if(event.matches)pictureAnimation?.cancel();});
 document.getElementById('fruit-save').onclick=()=>save(document.getElementById('fruit-label').value);document.getElementById('fruit-reset').onclick=()=>save('original');refresh();
})();

