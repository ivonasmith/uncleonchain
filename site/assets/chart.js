
(function(){
const LANG=document.documentElement.lang.startsWith('zh')?'zh':'en';
const ZH=LANG==='zh';
function nfmt(v,dp){return v.toLocaleString('en-US',{minimumFractionDigits:dp,maximumFractionDigits:dp})}
const M=s=>String(s).replace(/^-/,'−');
function usd(v){const a=Math.abs(v),s=v<0?'−':'';return a>=1e12?s+'$'+(a/1e12).toFixed(2)+'T':a>=1e9?s+'$'+(a/1e9).toFixed(2)+'B':a>=1e6?s+'$'+(a/1e6).toFixed(2)+'M':a>=1e3?s+'$'+(a/1e3).toFixed(1)+'K':s+'$'+Math.round(a)}
const sg=v=>v>0?'+':'';
const F={usd:usd,usds:v=>sg(v)+usd(v),pct:v=>M(v.toFixed(2))+'%',pct1:v=>M(v.toFixed(1))+'%',pcts:v=>sg(v)+M(v.toFixed(2))+'%',
 pp:v=>sg(v)+M(v.toFixed(2))+'pp',x:v=>M(v.toFixed(2)),xs:v=>sg(v)+M(v.toFixed(2)),x3:v=>M(v.toFixed(3)),int:v=>M(Math.round(v)+''),idx:v=>M(nfmt(v,2)),
 btc:v=>M(nfmt(Math.round(v),0))+' BTC',btcs:v=>sg(v)+M(nfmt(Math.round(v),0))+' BTC',price:v=>'$'+nfmt(Math.round(v),0)};
function axfmt(f,v){if(f==='usd'||f==='usds'||f==='price'){return usd(v)}
 if(f==='btc'||f==='btcs'){const a=Math.abs(v);return M(a>=1e6?(v/1e6).toFixed(2)+'M':a>=1e3?(v/1e3).toFixed(0)+'K':Math.round(v)+'')}
 if(f.startsWith('pct')||f==='pp')return M(Math.abs(v)<10?v.toFixed(1):v.toFixed(0))+(f==='pp'?'':'%');
 return M(Math.abs(v)>=1000?nfmt(v,0):(Math.abs(v)<10?v.toFixed(2):v.toFixed(1)))}
function nice(lo,hi,n){const span=hi-lo||Math.abs(hi)||1,step0=span/n,mag=Math.pow(10,Math.floor(Math.log10(step0))),r=step0/mag;
 const step=(r<1.5?1:r<3?2:r<7?5:10)*mag;const a=Math.floor(lo/step)*step,out=[];for(let v=a;v<=hi+step*.5;v+=step)if(v>=lo-step*.01)out.push(+v.toPrecision(12));return out}
const T0=d=>Date.UTC(+d.slice(0,4),+d.slice(5,7)-1,+d.slice(8,10));
const D0=t=>new Date(t).toISOString().slice(0,10);
const RANGES={'1M':31,'3M':92,'6M':183,'1Y':366,'3Y':1096,'5Y':1827,'ALL':0,'CYC':-1};
const RL={zh:{'1M':'1 月','3M':'3 月','6M':'6 月','1Y':'1 年','3Y':'3 年','5Y':'5 年','ALL':'全部','CYC':'本轮'},en:{'1M':'1M','3M':'3M','6M':'6M','1Y':'1Y','3Y':'3Y','5Y':'5Y','ALL':'All','CYC':'This cycle'}};
const groups={},cache={};
// 数据：旧格式 {d,s}；新格式（附录 C）{start|dates, values, level, extra}，可以是「归档 + 本月」两份拼起来
function norm(j){if(j.d)return j;let d=j.dates;const n=(j.values||[]).length||Object.values(j.extra||{}).reduce((a,x)=>Math.max(a,x.length),0);
 if(!d){d=[];if(j.start){let t=T0(j.start);for(let i=0;i<n;i++){d.push(D0(t));t+=864e5}}}
 const s={};if(j.values)s.v=j.values;if(j.level&&j.level.values)s.level=j.level.values;for(const k in (j.extra||{}))s[k]=j.extra[k];return {d:d,s:s,meta:j}}
function merge(parts){const out={d:[],s:{},meta:Object.assign({},...parts.map(p=>p.meta||{}))};
 parts.forEach(p=>{const n=p.d.length,base=out.d.length;out.d.push(...p.d);const ks=new Set([...Object.keys(out.s),...Object.keys(p.s)]);
  ks.forEach(k=>{if(!out.s[k])out.s[k]=new Array(base).fill(null);const a=p.s[k]||new Array(n).fill(null);out.s[k].push(...a)})});return out}
function get(u){if(!cache[u])cache[u]=fetch(u).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()}).catch(e=>{delete cache[u];throw e});return cache[u]}
function load(src){const us=Array.isArray(src)?src:[src];return Promise.all(us.map(u=>get(u).then(norm).catch(e=>{if(us.length>1&&u!==us[0])return {d:[],s:{}};throw e}))).then(merge)}
function mk(tag,attrs){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const k in attrs)e.setAttribute(k,attrs[k]);return e}
function q(sorted,p){if(!sorted.length)return null;const k=(sorted.length-1)*p,lo=Math.floor(k),hi=Math.ceil(k);return sorted[lo]+(sorted[hi]-sorted[lo])*(k-lo)}
const TONE={up:'up',dn:'dn',warn:'warn',neutral:'ink2',cool:'ink2'};

function Chart(el,cfg){if(!cfg.v2&&cfg.last===undefined)cfg.last=false;this.el=el;this.cfg=cfg;this.range=cfg.range||'ALL';this.mode=cfg.mode||'abs';this.off={};
 (cfg.series||[]).forEach(s=>{if(s.hidden)this.off[s.k]=1});this.init()}
Chart.prototype.init=function(){
 const c=this.cfg,el=this.el,self=this;el.classList.add('uc-chart');el.innerHTML='';
 const bar=document.createElement('div');bar.className='uc-bar';this.bar=bar;
 if(c.stack){const g=document.createElement('div');g.className='fg';
  [['abs',ZH?'金额':'Amount'],['pct',ZH?'份额 %':'Share %']].forEach(([m,l])=>{const b=document.createElement('button');
   b.className='pill';b.textContent=l;b.dataset.m=m;b.onclick=()=>{self.mode=m;self.draw()};g.appendChild(b)});bar.appendChild(g)}
 el.appendChild(bar);
 this.plot=document.createElement('div');this.plot.className='uc-plot';this.plot.style.minHeight=this.H()+'px';el.appendChild(this.plot);
 this.tip=document.createElement('div');this.tip.className='uc-tip';this.plot.appendChild(this.tip);
 this.leg=document.createElement('div');this.leg.className='legend';if(c.v2)el.appendChild(this.leg);else bar.appendChild(this.leg);
 if(c.note){const n=document.createElement('div');n.className='uc-note';n.textContent=c.note;el.appendChild(n)}
 if(c.group){(groups[c.group]=groups[c.group]||[]).push(this)}
 this.fetch();
 let t;new ResizeObserver(()=>{clearTimeout(t);t=setTimeout(()=>self.data&&self.draw(),80)}).observe(this.plot);
 window.addEventListener('uc-theme',()=>self.data&&self.draw());
};
Chart.prototype.H=function(){const w=this.plot?this.plot.clientWidth:this.el.clientWidth;return this.cfg.h||((w||800)<560?240:320)};
Chart.prototype.msg=function(text,retry){this.plot.querySelectorAll('svg,.uc-empty').forEach(x=>x.remove());const d=document.createElement('div');
 d.className='uc-empty';d.style.minHeight=this.H()+'px';d.textContent=text;if(retry){d.style.cursor='pointer';d.onclick=()=>this.fetch()}this.plot.insertBefore(d,this.tip)};
Chart.prototype.fetch=function(){const self=this,c=this.cfg;this.msg(ZH?'加载中…':'Loading…');
 const jobs=[load(c.src)];if(c.btc)jobs.push(load(c.btc).catch(()=>null));
 Promise.all(jobs).then(([j,b])=>{self.data=j;self.btc=b;self.buttons();self.draw()}).catch(()=>self.msg(ZH?'数据加载失败 · 点此重试':'Failed to load data · tap to retry',true))};
Chart.prototype.buttons=function(){const c=this.cfg,self=this,j=this.data;if(!c.ranges||!c.ranges.length||!j.d.length)return;
 const span=(T0(j.d[j.d.length-1])-T0(j.d[0]))/864e5;const g=document.createElement('div');g.className='fg';
 c.ranges.filter(r=>!c.v2||r==='ALL'||(r==='CYC'?!!c.cyc:span>RANGES[r]*1.02)).forEach(r=>{const b=document.createElement('button');b.className='pill';b.textContent=RL[LANG][r]||r;b.dataset.r=r;
  b.onclick=()=>{(c.group?groups[c.group]:[self]).forEach(x=>{if(x.data&&(r==='ALL'||x.bar.querySelector('[data-r="'+r+'"]'))){x.range=r;x.draw()}})};g.appendChild(b)});
 if(!g.querySelector('[data-r="'+this.range+'"]'))this.range='ALL';
 this.bar.insertBefore(g,this.bar.firstChild);
 if(c.hint){const h=document.createElement('span');h.className='uc-hint';h.textContent=c.hint;this.bar.appendChild(h)}};
Chart.prototype.draw=function(){
 const c=this.cfg,j=this.data,self=this;
 this.plot.querySelectorAll('.uc-empty').forEach(x=>x.remove());
 this.bar.querySelectorAll('.pill[data-r]').forEach(b=>b.classList.toggle('on',b.dataset.r===this.range));
 this.bar.querySelectorAll('.pill[data-m]').forEach(b=>b.classList.toggle('on',b.dataset.m===this.mode));
 const D=j.d,N=D.length;if(!N){this.msg(ZH?'暂无数据':'No data');return}
 const last=T0(D[N-1]);let lo0=0;
 if(this.range==='CYC'&&c.cyc)lo0=T0(c.cyc);else if(RANGES[this.range]>0)lo0=last-RANGES[this.range]*864e5;
 if(c.from&&T0(c.from)>lo0)lo0=T0(c.from);
 let i0=0;while(i0<N-1&&T0(D[i0])<lo0)i0++;
 const idx=[];for(let i=i0;i<N;i++)idx.push(i);
 const ser=(c.series||[]).filter(s=>j.s[s.k]);const vis=ser.filter(s=>!self.off[s.k]);
 const pct=c.stack&&this.mode==='pct';
 let stk=null,tot=null;
 if(c.stack){tot=idx.map(i=>vis.reduce((a,s)=>a+(j.s[s.k][i]||0),0));stk=[];let base=idx.map(()=>0);
  vis.forEach(s=>{const top=idx.map((i,n)=>{const v=j.s[s.k][i]||0;return base[n]+(pct?(tot[n]?v/tot[n]*100:0):v)});stk.push({lo:base,hi:top});base=top})}
 let lo=Infinity,hi=-Infinity;const all=[];
 if(c.stack){(stk.length?stk[stk.length-1].hi:[]).forEach(v=>{hi=Math.max(hi,v)});lo=0;if(pct)hi=100}
 else{const cf=c.clipFrom?T0(c.clipFrom):null;vis.forEach(s=>idx.forEach(i=>{const v=j.s[s.k][i];if(v!=null&&isFinite(v)&&(!c.log||v>0)){all.push(v)}}));
  if(c.clip&&cf){const inw=[];vis.forEach(s=>idx.forEach(i=>{const v=j.s[s.k][i];if(T0(D[i])>=cf&&v!=null&&isFinite(v))inw.push(v)}));
   if(inw.length>200){inw.sort((a,b)=>a-b);c._lo=q(inw,.005);c._hi=q(inw,.995)}else{c._lo=c._hi=null}}}
 if(!c.stack&&all.length){all.sort((a,b)=>a-b);if(c.clip&&c._lo!=null&&c.clipFrom){lo=c._lo;hi=c._hi;const a0=j.s[vis[0].k];for(let k=idx.length-1;k>=0;k--){const v=a0[idx[k]];if(v!=null){lo=Math.min(lo,v);hi=Math.max(hi,v);break}}}
  else if(c.clip&&all.length>200){lo=q(all,.005);hi=q(all,.995)}else{lo=all[0];hi=all[all.length-1]}}
 if(!isFinite(lo)||!isFinite(hi)){this.plot.querySelectorAll('svg').forEach(x=>x.remove());return}
 const clipped=c.clip&&!c.stack&&all.length&&(all[0]<lo||all[all.length-1]>hi);
 (c.lines||[]).forEach(l=>{if(l.v>=lo-(hi-lo)*.25&&l.v<=hi+(hi-lo)*.25){lo=Math.min(lo,l.v);hi=Math.max(hi,l.v)}});
 if(c.band&&c.bandOn!==false){lo=Math.min(lo,c.band.p10);hi=Math.max(hi,c.band.p90)}
 if(c.zero&&!c.log){lo=Math.min(lo,0);hi=Math.max(hi,0)}
 const W=Math.max(300,this.plot.clientWidth),H=this.H(),L=W<560?44:58,R=(c.lines&&c.lines.length)?(W<560?8:96):(c.last!==false?(W<560?8:70):12),TP=12,B=26;
 this.plot.style.minHeight=H+'px';
 const pw=W-L-R,ph=H-TP-B;
 let yt,Y,ylo,yhi;
 if(c.log){const a=Math.log10(lo),b=Math.log10(hi);const pad=(b-a)*.05||.1;const A=a-pad,Bv=b+pad;ylo=Math.pow(10,A);yhi=Math.pow(10,Bv);
  Y=v=>TP+ph*(1-(Math.log10(v)-A)/(Bv-A));yt=[];for(let e=Math.floor(A);e<=Math.ceil(Bv);e++)[1,2,5].forEach(m=>{const v=m*Math.pow(10,e);if(Math.log10(v)>=A&&Math.log10(v)<=Bv)yt.push(v)});
  if(yt.length>7)yt=yt.filter((v,k)=>String(v).startsWith('1'))}
 else{const pad=(hi-lo)*.06||Math.abs(hi)*.1||1;let a=lo-(c.stack||c.zero&&lo>=0?0:pad),b=hi+pad;if(pct){a=0;b=100}
  yt=nice(a,b,W<560?4:5);a=Math.min(a,yt[0]);b=Math.max(b,yt[yt.length-1]);ylo=a;yhi=b;Y=v=>TP+ph*(1-(v-a)/(b-a))}
 const YC=v=>Math.max(TP,Math.min(TP+ph,Y(v)));
 const t0=T0(D[idx[0]]),t1=T0(D[idx[idx.length-1]])||t0+1,X=t=>L+pw*((t-t0)/((t1-t0)||1));
 const svg=mk('svg',{viewBox:`0 0 ${W} ${H}`,height:H,role:'img','aria-label':c.title||''});
 // 区间背景带（颜色只按 bias）
 if(c.zone&&!c.stack&&!c.log){let prev=-Infinity;c.zone.forEach(z=>{const ub=z.ub==null?Infinity:z.ub,a=Math.max(prev,ylo),b=Math.min(ub,yhi);
  if(b>a&&TONE[z.t]&&z.t!=='neutral')svg.appendChild(mk('rect',{x:L,width:pw,y:Y(b),height:Math.max(0,Y(a)-Y(b)),style:`fill:var(--${TONE[z.t]});opacity:.06`}));prev=ub})}
 // 统计窗口外 / 历史回放区：浅灰底色
 (c.shade||[]).forEach(sh=>{const a=Math.max(t0,sh.from?T0(sh.from):t0),b=Math.min(t1,sh.to?T0(sh.to):t1);if(b<=a)return;
  svg.appendChild(mk('rect',{x:X(a),y:TP,width:X(b)-X(a),height:ph,style:'fill:var(--ink2);opacity:.07'}));
  if(sh.label&&X(b)-X(a)>90){const tx=mk('text',{x:X(a)+6,y:TP+12,class:'shl'});tx.textContent=sh.label;svg.appendChild(tx)}});
 // 状态背景色
 if(c.states&&c.stk&&j.s[c.stk]){const a=j.s[c.stk];let s0=0;
  for(let n=1;n<=idx.length;n++){if(n===idx.length||a[idx[n]]!==a[idx[s0]]){const st=c.states[a[idx[s0]]];
   if(st){const xa=X(T0(D[idx[s0]])),xb=n<idx.length?X(T0(D[idx[n]])):L+pw;svg.appendChild(mk('rect',{x:xa,y:TP,width:Math.max(0,xb-xa),height:ph,style:`fill:var(--${st.c});opacity:.14`}))}s0=n}}}
 yt.forEach(v=>{svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:Y(v),y2:Y(v),class:'gl'}));
  const tx=mk('text',{x:L-8,y:Y(v)+3.5,'text-anchor':'end',class:'ax'});tx.textContent=pct?v+'%':axfmt(c.fmt,v);svg.appendChild(tx)});
 // x 轴：3 年以上只标年；1~3 年标年-月；1 年以内标月-日
 const spanD=(t1-t0)/864e5,xt=[];
 {const d0=new Date(t0);let y=d0.getUTCFullYear(),m=d0.getUTCMonth();
  const stepM=spanD>1096?(spanD>3000?24:12):spanD>366?(spanD>700?6:3):spanD>120?1:0;
  if(stepM){m=Math.ceil(m/stepM)*stepM;while(true){const t=Date.UTC(y+Math.floor(m/12),m%12,1);if(t>t1)break;if(t>=t0)xt.push(t);m+=stepM}}
  else{for(let t=t0;t<=t1;t+=864e5*Math.max(1,Math.round(spanD/6)))xt.push(t)}}
 let lastX=-99;xt.forEach(t=>{const x=X(t);if(x-lastX<54)return;lastX=x;const d=new Date(t);
  const tx=mk('text',{x:x,y:TP+ph+18,'text-anchor':'middle',class:'ax'});
  tx.textContent=spanD>1096?d.getUTCFullYear()+'':spanD>366?d.getUTCFullYear()+'-'+String(d.getUTCMonth()+1).padStart(2,'0'):(d.getUTCMonth()+1)+'-'+String(d.getUTCDate()).padStart(2,'0');svg.appendChild(tx)});
 if(c.band&&!c.stack){const bd=c.band;
  svg.appendChild(mk('rect',{x:L,width:pw,y:YC(bd.p90),height:Math.max(0,YC(bd.p10)-YC(bd.p90)),style:'fill:var(--cool);opacity:.07'}));
  svg.appendChild(mk('rect',{x:L,width:pw,y:YC(bd.p75),height:Math.max(0,YC(bd.p25)-YC(bd.p75)),style:'fill:var(--cool);opacity:.10'}));
  svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:YC(bd.p50),y2:YC(bd.p50),style:'stroke:var(--cool);opacity:.5','stroke-dasharray':'2 3'}))}
 if(c.zero&&!c.log&&ylo<0&&yhi>0)svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:Y(0),y2:Y(0),class:'zero'}));
 (c.lines||[]).forEach(l=>{const y=Y(l.v);if(y<TP-1||y>TP+ph+1)return;
  svg.appendChild(mk('line',{x1:L,x2:L+pw,y1:y,y2:y,class:'thr',style:`stroke:var(--${TONE[l.tone]||'ink2'})`}));
  if(R>40){const tx=mk('text',{x:L+pw+6,y:y+3.5,class:'thl',style:`fill:var(--${TONE[l.tone]||'ink2'})`});tx.textContent=l.label;svg.appendChild(tx)}});
 // 竖线标记：减半、实时记录起点等
 (c.markers||[]).forEach(mm=>{const t=T0(mm.date);if(t<t0||t>t1)return;const x=X(t);
  svg.appendChild(mk('line',{x1:x,x2:x,y1:TP,y2:TP+ph,class:mm.type==='live'?'mk live':'mk'}));
  const tx=mk('text',{x:x+4,y:TP+ph-6,class:'mkl'});tx.textContent=mm.label||'';svg.appendChild(tx)});
 const col=s=>`var(--${s.c||'s1'})`;
 // 折线：点数远多于像素时按像素列取最小 / 最大值，形状不变
 function path(arr,clip){let p='',pen=false,n=0;const step=idx.length>pw*2?Math.ceil(idx.length/(pw*2)):1;
  for(let a=0;a<idx.length;a+=step){let bmin=null,bmax=null,imin=0,imax=0;for(let b=a;b<Math.min(idx.length,a+step);b++){const v=arr[idx[b]];
    if(v==null||!isFinite(v)||(c.log&&v<=0))continue;if(bmin==null||v<bmin){bmin=v;imin=b}if(bmax==null||v>bmax){bmax=v;imax=b}}
   if(bmin==null){if(c.gaps)pen=false;continue}
   const pts=imin<=imax?[[imin,bmin],[imax,bmax]]:[[imax,bmax],[imin,bmin]];
   pts.forEach(([b,v])=>{const yy=clip?YC(v):Y(v);p+=(pen?'L':'M')+X(T0(D[idx[b]])).toFixed(1)+','+yy.toFixed(1);pen=true;n++})}
  return p}
 if(c.stack){stk.forEach((st,k)=>{const s=vis[k];let p='';idx.forEach((i,n)=>{p+=(n?'L':'M')+X(T0(D[i])).toFixed(1)+','+Y(st.hi[n]).toFixed(1)});
   for(let n=idx.length-1;n>=0;n--)p+='L'+X(T0(D[idx[n]])).toFixed(1)+','+Y(st.lo[n]).toFixed(1);
   svg.appendChild(mk('path',{d:p+'Z',style:`fill:${col(s)};stroke:var(--card);stroke-width:${idx.length>200?0.5:1}`}))})}
 else vis.forEach(s=>{const arr=j.s[s.k];const p=path(arr,clipped);if(!p)return;
   if(s.area&&!c.log){const base=Y(Math.max(Math.min(0,yhi),ylo));svg.appendChild(mk('path',{d:p+`L${(L+pw).toFixed(1)},${base}L${L},${base}Z`,style:`fill:${col(s)};opacity:.10`}))}
   svg.appendChild(mk('path',{d:p,style:`fill:none;stroke:${col(s)};stroke-width:${s.w||1.8};stroke-linejoin:round;stroke-linecap:round`}))});
 // 被截掉的异常值：边缘画小三角，悬停看真实值
 if(clipped){const arr=j.s[vis[0].k];let lastx=-9;idx.forEach(i=>{const v=arr[i];if(v==null)return;const x=X(T0(D[i]));if(x-lastx<4)return;
   if(v>hi){svg.appendChild(mk('path',{d:`M${x-3},${TP+5}L${x+3},${TP+5}L${x},${TP}Z`,class:'clipm'}));lastx=x}
   else if(v<lo){svg.appendChild(mk('path',{d:`M${x-3},${TP+ph-5}L${x+3},${TP+ph-5}L${x},${TP+ph}Z`,class:'clipm'}));lastx=x}})}
 // 最新一个点：实心圆 + 当前值
 if(!c.stack&&c.last!==false&&vis.length){const s=vis[0],arr=j.s[s.k];let li=idx.length-1;while(li>=0&&(arr[idx[li]]==null))li--;
  if(li>=0){const v=arr[idx[li]],x=X(T0(D[idx[li]])),y=YC(v);svg.appendChild(mk('circle',{cx:x,cy:y,r:3.5,style:`fill:${col(s)};stroke:var(--card);stroke-width:1.5`}));
   if(R>40&&!(c.lines&&c.lines.length)){const tx=mk('text',{x:x+7,y:y+3.5,class:'lastv',style:`fill:${col(s)}`});tx.textContent=F[c.fmt](v);svg.appendChild(tx)}}}
 const xh=mk('line',{y1:TP,y2:TP+ph,class:'xh',visibility:'hidden'});svg.appendChild(xh);
 const dots=vis.map(s=>{const d=mk('circle',{r:4,style:`fill:${col(s)};stroke:var(--card);stroke-width:2`,visibility:'hidden'});svg.appendChild(d);return d});
 const hit=mk('rect',{x:L,y:TP,width:pw,height:ph,fill:'transparent'});svg.appendChild(hit);
 this.plot.querySelectorAll('svg').forEach(x=>x.remove());this.plot.insertBefore(svg,this.tip);
 // 图例（在图下方）：值跟最新一天；可开关的线点一下切换
 this.leg.innerHTML='';const li=idx[idx.length-1];
 if(ser.length>1||c.stack)ser.forEach(s=>{const sp=document.createElement(c.toggle?'button':'span'),i=document.createElement('i');i.className=c.stack?'box':'';i.style.background=col(s);
  if(c.toggle){sp.type='button';sp.className='lg'+(self.off[s.k]?' off':'');sp.setAttribute('aria-pressed',self.off[s.k]?'false':'true');sp.onclick=()=>{self.off[s.k]=self.off[s.k]?0:1;self.draw()}}
  sp.appendChild(i);sp.appendChild(document.createTextNode(s.n+' '));const b=document.createElement('b');let v=null;for(let k=idx.length-1;k>=0&&v==null;k--)v=j.s[s.k][idx[k]];
  b.textContent=v==null?'—':(c.stack&&pct?((tot[tot.length-1]?v/tot[tot.length-1]*100:0).toFixed(1)+'%'):F[c.fmt](v));sp.appendChild(b);this.leg.appendChild(sp)});
 const tsv=idx.map(i=>T0(D[i]));
 const bd=this.btc;let bts=null;if(bd&&bd.s.v)bts=bd.d.map(T0);
 function btcAt(t){if(!bts)return null;let a=0,b=bts.length-1;if(t<bts[0])return null;while(b-a>1){const m=(a+b)>>1;if(bts[m]<=t)a=m;else b=m}const k=bts[b]<=t?b:a;return bd.s.v[k]}
 function at(px){let a=0,b=tsv.length-1;const t=t0+(px-L)/pw*(t1-t0);while(b-a>1){const m=(a+b)>>1;if(tsv[m]<t)a=m;else b=m}return Math.abs(tsv[a]-t)<Math.abs(tsv[b]-t)?a:b}
 this.show=n=>{if(n==null||n<0){xh.setAttribute('visibility','hidden');dots.forEach(d=>d.setAttribute('visibility','hidden'));self.tip.style.display='none';return}
  const i=idx[n],x=X(tsv[n]);xh.setAttribute('x1',x);xh.setAttribute('x2',x);xh.setAttribute('visibility','visible');
  self.tip.innerHTML='';const hd=document.createElement('div');hd.className='td';hd.textContent=D[i]+' UTC'+(c.weekly?(ZH?' · 本周五读数':' · Friday reading'):'');self.tip.appendChild(hd);
  vis.forEach((s,k)=>{const v=j.s[s.k][i];const yv=c.stack?stk[k].hi[n]:v;
   if(yv!=null&&isFinite(yv)&&(!c.log||yv>0)){dots[k].setAttribute('cx',x);dots[k].setAttribute('cy',c.stack?Y(yv):YC(yv));dots[k].setAttribute('visibility','visible')}else dots[k].setAttribute('visibility','hidden');
   const r=document.createElement('div');r.className='tr';const ii=document.createElement('i');ii.style.background=col(s);const sp=document.createElement('span');sp.textContent=s.n;
   const b=document.createElement('b');b.textContent=v==null?'—':F[c.fmt](v)+(c.stack&&tot[n]?'  '+(v/tot[n]*100).toFixed(1)+'%':'');r.append(ii,sp,b);self.tip.appendChild(r)});
  if(c.stack){const r=document.createElement('div');r.className='tr';const sp=document.createElement('span');sp.textContent=ZH?'合计':'Total';
   const b=document.createElement('b');b.textContent=usd(tot[n]);r.append(document.createElement('i'),sp,b);self.tip.appendChild(r)}
  if(c.zone&&vis.length){const v=j.s[vis[0].k][i];if(v!=null){const z=c.zone.find(q=>q.ub==null||v<q.ub);if(z){const r=document.createElement('div');r.className='tr';
   const sp=document.createElement('span');sp.textContent=(ZH?'区间：':'Zone: ')+z.n;sp.style.color=`var(--${TONE[z.t]||'ink2'})`;r.append(sp);self.tip.appendChild(r)}}}
  if(c.states&&c.stk&&j.s[c.stk]){const st=c.states[j.s[c.stk][i]];if(st){const r=document.createElement('div');r.className='tr';
   const sp=document.createElement('span');sp.textContent=st.n;sp.style.color=`var(--${st.c})`;r.append(sp);self.tip.appendChild(r)}}
  if(bts){const bv=btcAt(tsv[n]);if(bv!=null){const r=document.createElement('div');r.className='tr';const sp=document.createElement('span');sp.textContent=ZH?'当天 BTC':'BTC that day';
   const b=document.createElement('b');b.textContent=F.price(bv);r.append(document.createElement('i'),sp,b);self.tip.appendChild(r)}}
  self.tip.style.display='block';const tw=self.tip.offsetWidth;let lx=x+14;if(lx+tw>W)lx=x-tw-14;self.tip.style.left=Math.max(0,lx)+'px';self.tip.style.top=(TP+4)+'px'};
 const move=e=>{const r=svg.getBoundingClientRect(),px=(e.clientX-r.left)*W/r.width;const n=at(px);const day=D[idx[n]];
  (c.group?groups[c.group]:[self]).forEach(g=>g.showDate?g.showDate(day):0)};
 const leave=e=>{if(e.pointerType==='touch')return;(c.group?groups[c.group]:[self]).forEach(g=>g.show&&g.show(null))};
 hit.addEventListener('pointermove',e=>{if(e.pointerType!=='touch')move(e)});hit.addEventListener('pointerdown',move);hit.addEventListener('pointerleave',leave);
 this.showDate=day=>{if(!self.show)return;const tt=T0(day);let best=-1,bd=Infinity;for(let n=0;n<tsv.length;n++){const d=Math.abs(tsv[n]-tt);if(d<bd){bd=d;best=n}}
  self.show(bd<=8*864e5?best:null)};
};
// 手机：点按图表显示读数，再点空白处关闭
document.addEventListener('pointerdown',e=>{if(e.target.closest&&e.target.closest('.uc-plot'))return;Object.values(groups).flat().forEach(g=>g.show&&g.show(null));
 document.querySelectorAll('.uc-chart').forEach(el=>{const t=el.querySelector('.uc-tip');if(t)t.style.display='none'})},{passive:true});
window.ucChart=function(el,cfg){return new Chart(el,cfg)};
// 进入视口才初始化（Tab 里隐藏的图不抢首屏）
function boot(el){if(el._uc)return;el._uc=1;try{window.ucChart(el,JSON.parse(el.getAttribute('data-chart')))}catch(e){console.error(e)}}
const io='IntersectionObserver' in window?new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){io.unobserve(e.target);boot(e.target)}}),{rootMargin:'200px'}):null;
document.querySelectorAll('[data-chart]').forEach(el=>{if(io)io.observe(el);else boot(el)});
window.ucBootCharts=root=>(root||document).querySelectorAll('[data-chart]').forEach(el=>{if(el.offsetParent!==null)boot(el)});
})();
