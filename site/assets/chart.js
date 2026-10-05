
(function(){
const LANG=document.documentElement.lang.startsWith('zh')?'zh':'en';
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
function nfmt(v,dp){return v.toLocaleString('en-US',{minimumFractionDigits:dp,maximumFractionDigits:dp})}
function usd(v){const a=Math.abs(v),s=v<0?'-':'';return a>=1e12?s+'$'+(a/1e12).toFixed(2)+'T':a>=1e9?s+'$'+(a/1e9).toFixed(2)+'B':a>=1e6?s+'$'+(a/1e6).toFixed(2)+'M':a>=1e3?s+'$'+(a/1e3).toFixed(1)+'K':s+'$'+Math.round(a)}
const sg=v=>v>0?'+':'';
const F={usd:usd,usds:v=>sg(v)+usd(v),pct:v=>v.toFixed(2)+'%',pct1:v=>v.toFixed(1)+'%',pcts:v=>sg(v)+v.toFixed(2)+'%',
 pp:v=>sg(v)+v.toFixed(2)+'pp',x:v=>v.toFixed(2),xs:v=>sg(v)+v.toFixed(2),x3:v=>v.toFixed(3),int:v=>Math.round(v)+'',idx:v=>nfmt(v,2),
 btc:v=>nfmt(Math.round(v),0)+' BTC',btcs:v=>sg(v)+nfmt(Math.round(v),0)+' BTC',price:v=>'$'+nfmt(Math.round(v),0)};
function axfmt(f,v){if(f==='usd'||f==='usds'||f==='price'){return usd(v)}
 if(f==='btc'||f==='btcs'){const a=Math.abs(v);return (a>=1e6?(v/1e6).toFixed(2)+'M':a>=1e3?(v/1e3).toFixed(0)+'K':Math.round(v)+'')}
 if(f.startsWith('pct')||f==='pp')return (Math.abs(v)<10?v.toFixed(1):v.toFixed(0))+(f==='pp'?'':'%');
 return Math.abs(v)>=1000?nfmt(v,0):(Math.abs(v)<10?v.toFixed(2):v.toFixed(1))}
function nice(lo,hi,n){const span=hi-lo||Math.abs(hi)||1,step0=span/n,mag=Math.pow(10,Math.floor(Math.log10(step0))),r=step0/mag;
 const step=(r<1.5?1:r<3?2:r<7?5:10)*mag;const a=Math.floor(lo/step)*step,out=[];for(let v=a;v<=hi+step*.5;v+=step)if(v>=lo-step*.01)out.push(+v.toPrecision(12));return out}
const T0=d=>Date.UTC(+d.slice(0,4),+d.slice(5,7)-1,+d.slice(8,10));
const RANGES={'1M':31,'3M':92,'6M':183,'1Y':366,'3Y':1096,'5Y':1827,'ALL':0};
const RL={zh:{'1M':'1 月','3M':'3 月','6M':'6 月','1Y':'1 年','3Y':'3 年','5Y':'5 年','ALL':'全部'},en:{'1M':'1M','3M':'3M','6M':'6M','1Y':'1Y','3Y':'3Y','5Y':'5Y','ALL':'All'}};
const groups={};
const cache={};
function load(src){if(!cache[src])cache[src]=fetch(src).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()});return cache[src]}
function mk(tag,attrs){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const k in attrs)e.setAttribute(k,attrs[k]);return e}

function Chart(el,cfg){this.el=el;this.cfg=cfg;this.range=cfg.range||'ALL';this.mode=cfg.mode||'abs';this.init()}
Chart.prototype.init=function(){
 const c=this.cfg,el=this.el,self=this;el.classList.add('uc-chart');el.innerHTML='';
 const bar=document.createElement('div');bar.className='uc-bar';
 if(c.ranges&&c.ranges.length){const g=document.createElement('div');g.className='fg';
  c.ranges.forEach(r=>{const b=document.createElement('button');b.className='pill';b.textContent=RL[LANG][r]||r;b.dataset.r=r;
   b.onclick=()=>{(c.group?groups[c.group]:[self]).forEach(x=>{x.range=r;x.draw()})};g.appendChild(b)});bar.appendChild(g)}
 if(c.stack){const g=document.createElement('div');g.className='fg';
  [['abs',LANG==='zh'?'金额':'Amount'],['pct',LANG==='zh'?'份额 %':'Share %']].forEach(([m,l])=>{const b=document.createElement('button');
   b.className='pill';b.textContent=l;b.dataset.m=m;b.onclick=()=>{self.mode=m;self.draw()};g.appendChild(b)});bar.appendChild(g)}
 this.leg=document.createElement('div');this.leg.className='legend';bar.appendChild(this.leg);
 el.appendChild(bar);
 this.plot=document.createElement('div');this.plot.className='uc-plot';el.appendChild(this.plot);
 this.tip=document.createElement('div');this.tip.className='uc-tip';this.plot.appendChild(this.tip);
 if(c.note){const n=document.createElement('div');n.className='uc-note';n.textContent=c.note;el.appendChild(n)}
 if(c.group){(groups[c.group]=groups[c.group]||[]).push(this)}
 load(c.src).then(j=>{self.data=j;self.draw()}).catch(e=>{self.plot.innerHTML='';const d=document.createElement('div');d.className='uc-empty';
  d.textContent=(LANG==='zh'?'走势数据还没生成（下一次每日运行后出现）':'Chart data not generated yet');self.plot.appendChild(d)});
 let t;new ResizeObserver(()=>{clearTimeout(t);t=setTimeout(()=>self.data&&self.draw(),80)}).observe(this.plot);
 window.addEventListener('uc-theme',()=>self.data&&self.draw());
};
Chart.prototype.draw=function(){
 const c=this.cfg,j=this.data,self=this;
 this.el.querySelectorAll('.pill[data-r]').forEach(b=>b.classList.toggle('on',b.dataset.r===this.range));
 this.el.querySelectorAll('.pill[data-m]').forEach(b=>b.classList.toggle('on',b.dataset.m===this.mode));
 const D=j.d,N=D.length;if(!N){return}
 const last=T0(D[N-1]),days=RANGES[this.range]||0;
 let i0=0;if(days){const lo=last-days*864e5;while(i0<N-1&&T0(D[i0])<lo)i0++}
 const idx=[];for(let i=i0;i<N;i++)idx.push(i);
 const ser=c.series.filter(s=>j.s[s.k]);
 const pct=c.stack&&this.mode==='pct';
 // 堆叠：逐日累加
 let stk=null,tot=null;
 if(c.stack){tot=idx.map(i=>ser.reduce((a,s)=>a+(j.s[s.k][i]||0),0));stk=[];let base=idx.map(()=>0);
  ser.forEach(s=>{const top=idx.map((i,n)=>{const v=j.s[s.k][i]||0;return base[n]+(pct?(tot[n]?v/tot[n]*100:0):v)});stk.push({lo:base,hi:top});base=top})}
 let lo=Infinity,hi=-Infinity;
 if(c.stack){stk[stk.length-1].hi.forEach(v=>{hi=Math.max(hi,v)});lo=0;if(pct)hi=100}
 else ser.forEach(s=>idx.forEach(i=>{const v=j.s[s.k][i];if(v!=null&&isFinite(v)&&(!c.log||v>0)){lo=Math.min(lo,v);hi=Math.max(hi,v)}}));
 if(!isFinite(lo)){this.plot.querySelectorAll('svg').forEach(x=>x.remove());return}
 (c.lines||[]).forEach(l=>{if(l.v>=lo-(hi-lo)*.25&&l.v<=hi+(hi-lo)*.25){lo=Math.min(lo,l.v);hi=Math.max(hi,l.v)}});
 if(c.band&&c.bandOn!==false){lo=Math.min(lo,c.band.p10);hi=Math.max(hi,c.band.p90)}
 if(c.zero&&!c.log){lo=Math.min(lo,0);hi=Math.max(hi,0)}
 const W=Math.max(320,this.plot.clientWidth),H=c.h||(W<560?220:280),L=W<560?46:58,R=(c.lines&&c.lines.length)||c.group?(W<560?8:96):12,TP=10,B=26;
 const pw=W-L-R,ph=H-TP-B;
 let yt,Y;
 if(c.log){const a=Math.log10(lo),b=Math.log10(hi);const pad=(b-a)*.05||.1;const A=a-pad,Bv=b+pad;
  Y=v=>TP+ph*(1-(Math.log10(v)-A)/(Bv-A));yt=[];for(let e=Math.floor(A);e<=Math.ceil(Bv);e++)[1,2,5].forEach(m=>{const v=m*Math.pow(10,e);if(Math.log10(v)>=A&&Math.log10(v)<=Bv)yt.push(v)});
  if(yt.length>7)yt=yt.filter((v,k)=>String(v).startsWith('1'))}
 else{const pad=(hi-lo)*.06||Math.abs(hi)*.1||1;let a=lo-(c.stack||c.zero&&lo>=0?0:pad),b=hi+pad;if(pct){a=0;b=100}
  yt=nice(a,b,W<560?4:5);a=Math.min(a,yt[0]);b=Math.max(b,yt[yt.length-1]);Y=v=>TP+ph*(1-(v-a)/(b-a))}
 const t0=T0(D[idx[0]]),t1=T0(D[idx[idx.length-1]])||t0+1,X=t=>L+pw*((t-t0)/((t1-t0)||1));
 const svg=mk('svg',{viewBox:`0 0 ${W} ${H}`,height:H,role:'img','aria-label':c.title||''});
 yt.forEach(v=>{svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:Y(v),y2:Y(v),class:'gl'}));
  const tx=mk('text',{x:L-8,y:Y(v)+3.5,'text-anchor':'end',class:'ax'});tx.textContent=pct?v+'%':axfmt(c.fmt,v);svg.appendChild(tx)});
 // x 轴刻度：按跨度选日 / 月 / 年
 const spanD=(t1-t0)/864e5,xt=[];
 {const d0=new Date(t0),d1=new Date(t1);let y=d0.getUTCFullYear(),m=d0.getUTCMonth();
  const stepM=spanD>3000?24:spanD>1400?12:spanD>700?6:spanD>300?3:spanD>120?1:0;
  if(stepM){m=Math.ceil(m/stepM)*stepM;while(true){const t=Date.UTC(y+Math.floor(m/12),m%12,1);if(t>t1)break;if(t>=t0)xt.push(t);m+=stepM}}
  else{for(let t=t0;t<=t1;t+=864e5*Math.max(1,Math.round(spanD/6)))xt.push(t)}}
 let lastX=-99;xt.forEach(t=>{const x=X(t);if(x-lastX<54)return;lastX=x;const d=new Date(t);
  const tx=mk('text',{x:x,y:TP+ph+18,'text-anchor':'middle',class:'ax'});
  tx.textContent=spanD>300?(d.getUTCMonth()===0||spanD>1400?d.getUTCFullYear()+'':(d.getUTCFullYear()%100)+'-'+String(d.getUTCMonth()+1).padStart(2,'0')):(d.getUTCMonth()+1)+'/'+d.getUTCDate();svg.appendChild(tx)});
 // 正常波动带：p10–p90 浅、p25–p75 深、中位虚线
 if(c.band&&!c.stack){const bd=c.band;
  svg.appendChild(mk('rect',{x:L,width:pw,y:Y(bd.p90),height:Math.max(0,Y(bd.p10)-Y(bd.p90)),style:'fill:var(--cool);opacity:.07'}));
  svg.appendChild(mk('rect',{x:L,width:pw,y:Y(bd.p75),height:Math.max(0,Y(bd.p25)-Y(bd.p75)),style:'fill:var(--cool);opacity:.10'}));
  svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:Y(bd.p50),y2:Y(bd.p50),style:'stroke:var(--cool);opacity:.5','stroke-dasharray':'2 3'}))}
 if(c.zero&&!c.log&&lo<0&&hi>0)svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:Y(0),y2:Y(0),class:'zero'}));
 // 区间阈值线 + 右侧标签
 (c.lines||[]).forEach(l=>{const y=Y(l.v);if(y<TP-1||y>TP+ph+1)return;
  svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:y,y2:y,class:'thr',style:`stroke:var(--${l.tone==='neutral'?'ink2':l.tone})`}));
  if(R>40){const tx=mk('text',{x:L+pw+6,y:y+3.5,class:'thl',style:`fill:var(--${l.tone==='neutral'?'ink2':l.tone})`});tx.textContent=l.label;svg.appendChild(tx)}});
 // 序列
 const col=s=>`var(--${s.c||'s1'})`;
 if(c.stack){stk.forEach((st,k)=>{const s=ser[k];let p='';idx.forEach((i,n)=>{p+=(n?'L':'M')+X(T0(D[i])).toFixed(1)+','+Y(st.hi[n]).toFixed(1)});
   for(let n=idx.length-1;n>=0;n--)p+='L'+X(T0(D[idx[n]])).toFixed(1)+','+Y(st.lo[n]).toFixed(1);
   svg.appendChild(mk('path',{d:p+'Z',style:`fill:${col(s)};stroke:var(--card);stroke-width:${idx.length>200?0.5:1}`}))})}
 else ser.forEach(s=>{let p='',pen=false;const arr=j.s[s.k];idx.forEach(i=>{const v=arr[i];if(v==null||!isFinite(v)||(c.log&&v<=0)){pen=false;return}
   p+=(pen?'L':'M')+X(T0(D[i])).toFixed(1)+','+Y(v).toFixed(1);pen=true});
   if(s.area&&!c.log){const base=Y(Math.max(Math.min(0,hi),lo));svg.appendChild(mk('path',{d:p+`L${(L+pw).toFixed(1)},${base}L${L},${base}Z`,style:`fill:${col(s)};opacity:.10`}))}
   svg.appendChild(mk('path',{d:p,style:`fill:none;stroke:${col(s)};stroke-width:${s.w||1.8};stroke-linejoin:round;stroke-linecap:round`}))});
 // 十字线
 const xh=mk('line',{y1:TP,y2:TP+ph,class:'xh',visibility:'hidden'});svg.appendChild(xh);
 const dots=ser.map(s=>{const d=mk('circle',{r:4,style:`fill:${col(s)};stroke:var(--card);stroke-width:2`,visibility:'hidden'});svg.appendChild(d);return d});
 const hit=mk('rect',{x:L,y:TP,width:pw,height:ph,fill:'transparent'});svg.appendChild(hit);
 this.plot.querySelectorAll('svg').forEach(x=>x.remove());this.plot.insertBefore(svg,this.tip);
 // 图例：值跟最新一天
 this.leg.innerHTML='';const li=idx[idx.length-1];
 if(ser.length>1||c.stack)ser.forEach(s=>{const sp=document.createElement('span'),i=document.createElement('i');i.className=c.stack?'box':'';i.style.background=col(s);
  sp.appendChild(i);sp.appendChild(document.createTextNode(s.n+' '));const b=document.createElement('b');const v=j.s[s.k][li];
  b.textContent=v==null?'—':(c.stack&&pct?((tot[tot.length-1]?v/tot[tot.length-1]*100:0).toFixed(1)+'%'):F[c.fmt](v));sp.appendChild(b);this.leg.appendChild(sp)});
 const tsv=idx.map(i=>T0(D[i]));
 function at(px){let a=0,b=tsv.length-1;const t=t0+(px-L)/pw*(t1-t0);while(b-a>1){const m=(a+b)>>1;if(tsv[m]<t)a=m;else b=m}return Math.abs(tsv[a]-t)<Math.abs(tsv[b]-t)?a:b}
 this.show=n=>{if(n==null||n<0){xh.setAttribute('visibility','hidden');dots.forEach(d=>d.setAttribute('visibility','hidden'));self.tip.style.display='none';return}
  const i=idx[n],x=X(tsv[n]);xh.setAttribute('x1',x);xh.setAttribute('x2',x);xh.setAttribute('visibility','visible');
  self.tip.innerHTML='';const hd=document.createElement('div');hd.className='td';hd.textContent=D[i];self.tip.appendChild(hd);
  ser.forEach((s,k)=>{const v=j.s[s.k][i];const yv=c.stack?stk[k].hi[n]:v;
   if(yv!=null&&isFinite(yv)&&(!c.log||yv>0)){dots[k].setAttribute('cx',x);dots[k].setAttribute('cy',Y(yv));dots[k].setAttribute('visibility','visible')}else dots[k].setAttribute('visibility','hidden');
   const r=document.createElement('div');r.className='tr';const ii=document.createElement('i');ii.style.background=col(s);const sp=document.createElement('span');sp.textContent=s.n;
   const b=document.createElement('b');b.textContent=v==null?'—':F[c.fmt](v)+(c.stack&&tot[n]?'  '+(v/tot[n]*100).toFixed(1)+'%':'');r.append(ii,sp,b);self.tip.appendChild(r)});
  if(c.stack){const r=document.createElement('div');r.className='tr';const sp=document.createElement('span');sp.textContent=LANG==='zh'?'合计':'Total';
   const b=document.createElement('b');b.textContent=usd(tot[n]);r.append(document.createElement('i'),sp,b);self.tip.appendChild(r)}
  if(c.zone){const v=j.s[ser[0].k][i];if(v!=null){const z=c.zone.find(q=>q.ub==null||v<q.ub);if(z){const r=document.createElement('div');r.className='tr';
   const sp=document.createElement('span');sp.textContent=z.n;sp.style.color=`var(--${z.t==='neutral'?'ink2':z.t})`;r.append(sp);self.tip.appendChild(r)}}}
  self.tip.style.display='block';const tw=self.tip.offsetWidth;let lx=x+14;if(lx+tw>W)lx=x-tw-14;self.tip.style.left=Math.max(0,lx)+'px';self.tip.style.top=(TP+4)+'px'};
 const move=e=>{const r=svg.getBoundingClientRect(),px=(e.clientX-r.left)*W/r.width;const n=at(px);const day=D[idx[n]];
  (c.group?groups[c.group]:[self]).forEach(g=>g.showDate?g.showDate(day):0)};
 const leave=()=>{(c.group?groups[c.group]:[self]).forEach(g=>g.show&&g.show(null))};
 hit.addEventListener('pointermove',move);hit.addEventListener('pointerdown',move);hit.addEventListener('pointerleave',leave);
 this.showDate=day=>{const tt=T0(day);let best=-1,bd=Infinity;for(let n=0;n<tsv.length;n++){const d=Math.abs(tsv[n]-tt);if(d<bd){bd=d;best=n}}
  self.show(bd<=8*864e5?best:null)};
};
window.ucChart=function(el,cfg){return new Chart(el,cfg)};
document.querySelectorAll('[data-chart]').forEach(el=>{try{window.ucChart(el,JSON.parse(el.getAttribute('data-chart')))}catch(e){console.error(e)}});
})();
