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
