(() => {
 const tip=document.getElementById('report-chart-tooltip');
 function show(text,x,y){tip.textContent=text;tip.hidden=false;tip.style.left=Math.max(8,Math.min(x+12,innerWidth-260))+'px';tip.style.top=Math.max(8,Math.min(y+14,innerHeight-75))+'px';}
 function hide(){tip.hidden=true;}
 document.querySelectorAll('[data-chart-tip]').forEach(el=>{
  el.addEventListener('pointermove',e=>show(el.dataset.chartTip,e.clientX,e.clientY));
  el.addEventListener('pointerleave',hide);
  function focus(){const r=el.getBoundingClientRect();show(el.dataset.chartTip,r.left,r.top);}
  el.addEventListener('focus',focus);el.addEventListener('click',focus);el.addEventListener('blur',hide);
 });
 const donut=document.getElementById('interactive-donut');
 if(donut){const rows=JSON.parse(document.getElementById('report-distribution-data').textContent);
  function inspect(e){const r=donut.getBoundingClientRect(),x=e.clientX-r.left-r.width/2,y=e.clientY-r.top-r.height/2;const distance=Math.hypot(x,y);if(distance<r.width*.3||distance>r.width*.5){hide();return;}const pct=((Math.atan2(y,x)*180/Math.PI+450)%360)/3.6;const row=rows.find(row=>pct>=row.start&&pct<row.end);if(row)show(row.label+': '+row.pct+'%',e.clientX,e.clientY);}
  donut.addEventListener('pointermove',inspect);donut.addEventListener('click',inspect);donut.addEventListener('pointerleave',hide);
  donut.addEventListener('focus',()=>{const r=donut.getBoundingClientRect();show(rows.map(row=>row.label+': '+row.pct+'%').join(' | '),r.left,r.top);});donut.addEventListener('blur',hide);
 }
 document.addEventListener('keydown',e=>{if(e.key==='Escape')hide();});window.addEventListener('scroll',hide,{passive:true});
})();

// Place each saved percentage at the midpoint of its donut segment.
(() => {
 const donut=document.getElementById('interactive-donut');
 if(!donut)return;
 const rows=JSON.parse(document.getElementById('report-distribution-data').textContent);
 rows.filter(row=>row.pct>=4).forEach(row=>{
  const angle=((row.start+row.end)/2)*Math.PI/50-Math.PI/2;
  const label=document.createElement('span');label.className='report-donut-label';
  label.textContent=row.pct.toFixed(1)+'%';label.setAttribute('aria-hidden','true');
  label.style.left=(50+41*Math.cos(angle))+'%';label.style.top=(50+41*Math.sin(angle))+'%';donut.append(label);
 });
})();

// Swipe between report charts on mobile; dots also support keyboard navigation.
(() => {
 const track=document.querySelector('.analytics-charts');if(!track)return;
 const cards=[...track.querySelectorAll('.analytics-card')];
 const nav=document.createElement('div');nav.className='reports-chart-navigation';nav.setAttribute('role','group');nav.setAttribute('aria-label','Choose report graph');
 const hint=document.createElement('p');hint.className='reports-chart-swipe-hint';hint.textContent='Swipe to explore the graphs';
 const mobile=matchMedia('(max-width:760px)'), reduce=matchMedia('(prefers-reduced-motion:reduce)');
 const dots=cards.map((card,index)=>{
  const button=document.createElement('button');button.type='button';button.setAttribute('aria-label',card.querySelector('h2').textContent.trim());button.setAttribute('aria-pressed',String(index===0));
  button.onclick=()=>track.scrollTo({left:card.offsetLeft-cards[0].offsetLeft,behavior:reduce.matches?'auto':'smooth'});nav.append(button);return button;
 });
 track.after(hint,nav);
 let scheduled=false;
 function sync(){scheduled=false;const origin=cards[0].offsetLeft;let closest=0;cards.forEach((card,i)=>{if(Math.abs(card.offsetLeft-origin-track.scrollLeft)<Math.abs(cards[closest].offsetLeft-origin-track.scrollLeft))closest=i;});dots.forEach((dot,i)=>dot.setAttribute('aria-pressed',String(i===closest)));}
 track.addEventListener('scroll',()=>{if(!scheduled){scheduled=true;requestAnimationFrame(sync);}},{passive:true});
 mobile.addEventListener('change',()=>{track.scrollLeft=0;sync();});window.addEventListener('resize',sync);sync();
})();
