
const DATA=JSON.parse(document.getElementById('agent-data').textContent);
const fmt=(v,d=0)=>v==null?'U':Number(v).toLocaleString('zh-CN',{maximumFractionDigits:d});
const rows=DATA.rows,last=rows[rows.length-1];
document.getElementById('through').textContent='数据截至 '+DATA.data_through_utc+' UTC';
document.getElementById('updated').textContent='数据读取完成 '+(DATA.source_read_through_utc||'U').replace('T',' ').slice(0,19)+' UTC';
const currentUTC=new Date().toISOString().slice(0,10), gap=(Date.parse(currentUTC)-Date.parse(DATA.data_through_utc))/86400000;
if(gap>1){document.getElementById('lag').textContent='当前快照距今日 '+gap+' 个 UTC 日';document.getElementById('lag').className='lag';}
const scope=(last.scope||[]).join('、')||'U';
const totalVolume=rows.every(r=>r.volume_bnb!=null&&JSON.stringify(r.scope)===JSON.stringify(last.scope))?rows.reduce((a,r)=>a+Number(r.volume_bnb),0):null;
document.getElementById('coverage').textContent='注册数据覆盖完整注册表；交易及发币数据目前覆盖 '+scope+'，不代表全生态总量。';
const specs=[['cumulative_ids','累计 Agent ID','截至最近完整日',0,'个'],['new_ids','当日新增 Agent ID','完整 UTC 日新增',0,'个'],['trading_addresses','当日交易地址','已核平台 · '+scope,0,'个'],['volume_bnb','当日成交额','已核曲线 · '+scope,6,'BNB'],['new_launches','当日新发币','已核平台 · '+scope,0,'个'],['graduated','当日毕业币','已核平台 · '+scope,0,'个']];
for(const [key,label,sub,dec,unit] of specs){const div=document.createElement('article');div.className='card';const l=document.createElement('div');l.className='label';l.textContent=label;const v=document.createElement('div');v.className='value';v.textContent=fmt(last[key],dec)+' ';const u=document.createElement('span');u.className='unit';u.textContent=unit;v.appendChild(u);const s=document.createElement('div');s.className='sub';s.textContent=sub+(key==='volume_bnb'?' · 观测期累计 '+fmt(totalVolume,6)+' BNB':'');div.append(l,v,s);document.getElementById('cards').appendChild(div);}
function render(range){
 const sample=range==='all'?rows:rows.slice(-Number(range));document.getElementById('charts').replaceChildren();
 for(const [key,label,sub,dec,unit] of specs){
  const scoped=!['cumulative_ids','new_ids'].includes(key), stable=JSON.stringify(last.scope);
  const values=sample.map(r=>scoped&&JSON.stringify(r.scope)!==stable?null:r[key]);
  const valid=values.filter(v=>v!=null).map(Number), W=520,H=220,L=59,R=16,T=20,B=40;
  const plotW=W-L-R,plotH=H-T-B,max=valid.length?Math.max(...valid):0,top=max>0?max*1.15:1;
  const x=i=>L+(i+.5)*plotW/sample.length,y=v=>H-B-Number(v)/top*plotH;
  const axisLabel=v=>v>=1000000?(v/1000000).toFixed(1)+'m':v>=10000?(v/1000).toFixed(0)+'k':fmt(v,key==='volume_bnb'?3:0);
  let svg='<svg class="chart" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+label+'趋势">';
  for(let i=0;i<=3;i++){let n=top*i/3,yy=y(n);svg+='<line x1="'+L+'" x2="'+(W-R)+'" y1="'+yy+'" y2="'+yy+'" stroke="#edf1f5"/><text x="'+(L-9)+'" y="'+(yy+4)+'" text-anchor="end" fill="#8c9aa5" font-size="10">'+axisLabel(n)+'</text>';}
  const bar=['new_ids','new_launches','graduated'].includes(key);
  if(bar){values.forEach((v,i)=>{if(v==null)return;let xx=x(i),yy=y(v),bw=Math.max(1,Math.min(26,plotW/sample.length*.55));svg+='<rect x="'+(xx-bw/2)+'" y="'+yy+'" width="'+bw+'" height="'+(H-B-yy)+'" rx="2" fill="#14998b"><title>'+sample[i].date+' · '+fmt(v,dec)+' '+unit+'</title></rect>';if(Number(v)===0)svg+='<circle cx="'+xx+'" cy="'+yy+'" r="2" fill="#14998b"/>';});}
  else{let path='',open=false;values.forEach((v,i)=>{if(v==null){open=false;return;}path+=(open?' L':' M')+x(i)+' '+y(v);open=true;});svg+='<path d="'+path+'" fill="none" stroke="#4175c8" stroke-width="2.3"/>';values.forEach((v,i)=>{if(v==null)return;svg+='<circle cx="'+x(i)+'" cy="'+y(v)+'" r="3" fill="#4175c8"><title>'+sample[i].date+' · '+fmt(v,dec)+' '+unit+'</title></circle>';});}
  const step=Math.max(1,Math.ceil(sample.length/5));sample.forEach((r,i)=>{if(i%step===0||i===sample.length-1)svg+='<text x="'+x(i)+'" y="'+(H-13)+'" text-anchor="middle" font-size="10" fill="#8c9aa5">'+r.date.slice(5)+'</text>';});
  if(!valid.length)svg+='<text x="'+(W/2)+'" y="'+(H/2)+'" text-anchor="middle" class="empty">U · 暂无完整数据</text>';
  svg+='</svg>';const panel=document.createElement('article');panel.className='panel';const h=document.createElement('h3');h.textContent=label+' · '+unit;const p=document.createElement('p');p.textContent=(scoped?'已核范围：'+scope:'完整 Agent ID 注册表')+' · UTC';panel.append(h,p);panel.insertAdjacentHTML('beforeend',svg);document.getElementById('charts').appendChild(panel);
 }
}
document.querySelectorAll('[data-range]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-range]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));render(b.dataset.range);}));render('all');
