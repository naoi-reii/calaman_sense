(() => {
 const dialog=document.getElementById('fruit-inspector'), fruits=[];
 const labels={unripe:'Unripe',ripe:'Ripe',overripe:'Overripe'};
 const motion=matchMedia('(prefers-reduced-motion: reduce)'), zoom=document.getElementById('fruit-zoom-level');
 let inspectorFilter='all';
 let active=0, filter='all', busy=false, opener=null, pictureAnimation=null, drawCurrent=()=>{};
 function animate(element, frames){if(!motion.matches&&element.animate)return element.animate(frames,{duration:330,easing:'cubic-bezier(.22,1,.36,1)'});}
 document.querySelectorAll('.result-figure[data-image-id]').forEach((figure,imageIndex)=>{
  const data=figure.querySelectorAll('script[type="application/json"]');
  const group={figure, image:figure.querySelector('img'), boxes:JSON.parse(data[0].textContent), corrections:JSON.parse(data[1].textContent), number:imageIndex+1};

  figure.querySelectorAll('[data-fruit-index]').forEach(button=>{
   const index=Number(button.dataset.fruitIndex), fruit={group,index,button,box:group.boxes[index]};
   button.addEventListener('click',()=>{if(busy)return;opener=button;active=fruits.indexOf(fruit);inspectorFilter='all';dialog.showModal();document.body.classList.add('fruit-inspector-open');show();animate(dialog,[{opacity:0,transform:'translateY(22px) scale(.97)'},{opacity:1,transform:'translateY(0) scale(1)'}]);});fruits.push(fruit);
  });
 });
 function current(f){return f.group.corrections[String(f.index)] || f.box.css_class;}
 function inspectedFruits(){return fruits.filter(f=>inspectorFilter==='all'||current(f)===inspectorFilter);}
 function updateInspectorControls(){
  const matching=inspectedFruits(), position=matching.indexOf(fruits[active]);
  document.getElementById('fruit-prev').disabled=busy||position<=0;
  document.getElementById('fruit-next').disabled=busy||position<0||position>=matching.length-1;
  dialog.querySelectorAll('[data-inspector-filter]').forEach(button=>{
   const key=button.dataset.inspectorFilter;
   button.setAttribute('aria-pressed',String(key===inspectorFilter));
   button.disabled=busy||!fruits.some(f=>key==='all'||current(f)===key);
   button.title=button.disabled&&!busy?'No '+labels[key].toLowerCase()+' fruits':'';
  });
 }
 dialog.querySelectorAll('[data-inspector-filter]').forEach(button=>button.addEventListener('click',()=>{
  if(busy)return;inspectorFilter=button.dataset.inspectorFilter;
  const matching=inspectedFruits();if(!matching.includes(fruits[active]))active=fruits.indexOf(matching[0]);show();
 }));
 function refresh(){
  let matches=0;
  fruits.forEach(f=>{const key=current(f), match=filter==='all'||key===filter;matches+=Number(match); f.button.classList.toggle('fruit-dimmed',!match); f.button.classList.toggle('fruit-highlighted',match&&filter!=='all');f.button.classList.remove('bbox-unripe','bbox-ripe','bbox-overripe');f.button.classList.add('bbox-'+key);f.button.setAttribute('aria-label',`Inspect image ${f.group.number}, fruit ${f.index+1}: ${labels[key]||key}`); f.button.querySelector('.bounding-box-label').textContent=f.group.corrections[String(f.index)] ? `${labels[key]} (reviewed)` : f.box.label||labels[key];});
  document.getElementById('fruit-filter-status').textContent=fruits.length?`${matches} of ${fruits.length} fruits highlighted across all images.`:'No per-fruit detections are available for this scan.';

 }
 function show(){
  let matching=inspectedFruits();if(!matching.length){inspectorFilter='all';matching=inspectedFruits();}
  if(!matching.includes(fruits[active]))active=fruits.indexOf(matching[0]);
  const f=fruits[active];if(!f)return;updateInspectorControls();
  zoom.value='1';document.getElementById('fruit-zoom-value').textContent='1.0×';
  document.getElementById('fruit-number').textContent='Fruit ' + (f.index+1);
  document.getElementById('inspector-position').textContent=`Image ${f.group.number} | Fruit ${f.index+1} | ${matching.indexOf(f)+1} of ${matching.length}`;
  document.getElementById('inspector-original').textContent=''+(f.box.label||labels[f.box.css_class]||'Unknown')+( /\d/.test(f.box.label||'')?'':' | Score unavailable');
  document.getElementById('fruit-label').value=current(f);
  document.getElementById('inspector-status').textContent='';
  updateInspectorControls();
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
  try{const cookie=document.cookie.split(';').map(part=>part.trim()).find(part=>part.startsWith('csrftoken='));const token=cookie?cookie.slice(10):dialog.querySelector('[name=csrfmiddlewaretoken]').value;const body=new URLSearchParams({image_id:f.group.figure.dataset.imageId,index:f.index,label});const response=await fetch(location.pathname,{method:'POST',headers:{'X-CSRFToken':token},body});if(!response.ok)throw Error();const data=await response.json();f.group.corrections=data.corrections;refresh();show();document.getElementById('inspector-status').textContent='Correction saved.';}catch(_){document.getElementById('inspector-status').textContent='Could not save. Please try again. Your original result is unchanged.';}finally{busy=false;controls.forEach(b=>b.disabled=false);updateInspectorControls();}
 }
 document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));refresh();}));
 document.getElementById('inspector-close').onclick=()=>{if(!busy)dialog.close();};dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
 dialog.addEventListener('close',()=>{pictureAnimation?.cancel();document.body.classList.remove('fruit-inspector-open');opener?.focus({preventScroll:true});});
 function navigate(direction){const matching=inspectedFruits(),next=matching.indexOf(fruits[active])+direction;if(busy||next<0||next>=matching.length)return;active=fruits.indexOf(matching[next]);show();}
 document.getElementById('fruit-prev').onclick=()=>navigate(-1);document.getElementById('fruit-next').onclick=()=>navigate(1);
 zoom.addEventListener('input',()=>{document.getElementById('fruit-zoom-value').textContent=Number(zoom.value).toFixed(1)+'×';drawCurrent();});
 dialog.addEventListener('keydown',event=>{if(event.target.closest('input,select,textarea')||!['ArrowLeft','ArrowRight'].includes(event.key))return;event.preventDefault();navigate(event.key==='ArrowRight'?1:-1);});
 const photo=document.getElementById('fruit-zoom'), pointers=new Map();let gesture=null,pinch=null;
 function separation(){const [a,b]=[...pointers.values()];return Math.hypot(a.x-b.x,a.y-b.y);}
 photo.addEventListener('pointerdown',event=>{
  if(event.button!==0||busy)return;
  pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});photo.setPointerCapture(event.pointerId);
  if(pointers.size===1)gesture={x:event.clientX,y:event.clientY,id:event.pointerId};
  else {gesture=null;if(pointers.size===2)pinch={distance:separation(),zoom:Number(zoom.value)};}
 });
 photo.addEventListener('pointermove',event=>{
  if(!pointers.has(event.pointerId))return;
  pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
  if(!busy&&pointers.size===2&&pinch?.distance>0){zoom.value=String(Math.max(Number(zoom.min),Math.min(Number(zoom.max),pinch.zoom*separation()/pinch.distance)));zoom.dispatchEvent(new Event('input'));}
 });
 function finish(event){
  if(event.type==='pointerup'&&gesture?.id===event.pointerId){const dx=event.clientX-gesture.x,dy=event.clientY-gesture.y;if(Math.abs(dx)>45&&Math.abs(dx)>Math.abs(dy)*1.3)navigate(dx<0?1:-1);}
  pointers.delete(event.pointerId);gesture=null;pinch=null;
 }
 ['pointerup','pointercancel','lostpointercapture'].forEach(name=>photo.addEventListener(name,finish));
 dialog.addEventListener('close',()=>{pointers.clear();gesture=null;pinch=null;});
 motion.addEventListener('change',event=>{if(event.matches)pictureAnimation?.cancel();});
 document.getElementById('fruit-save').onclick=()=>save(document.getElementById('fruit-label').value);document.getElementById('fruit-reset').onclick=()=>save('original');refresh();
})();

