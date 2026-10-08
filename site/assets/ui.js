
(function(){
const root=document.documentElement;
function setT(t){root.setAttribute('data-theme',t);try{localStorage.setItem('uc-theme',t)}catch(e){}
 document.querySelectorAll('.thm').forEach(b=>b.setAttribute('aria-pressed',t==='light'?'true':'false'));
 window.dispatchEvent(new Event('uc-theme'))}
document.querySelectorAll('.thm').forEach(b=>b.addEventListener('click',()=>setT(root.getAttribute('data-theme')==='light'?'dark':'light')));
// 预取：鼠标停在站内链接上 65ms，或手指按下，就提前下载那一页
const seen=new Set([location.pathname]);let tm=null;
function pf(a){if(!a||!a.href)return;let u;try{u=new URL(a.href)}catch(e){return}
 if(u.origin!==location.origin||seen.has(u.pathname)||a.target==='_blank'||/\.(png|jpe?g|svg|json)$/.test(u.pathname))return;
 seen.add(u.pathname);const l=document.createElement('link');l.rel='prefetch';l.href=u.pathname;document.head.appendChild(l)}
document.addEventListener('mouseover',e=>{const a=e.target.closest&&e.target.closest('a[href]');if(!a)return;clearTimeout(tm);tm=setTimeout(()=>pf(a),65)},{passive:true});
document.addEventListener('mouseout',()=>clearTimeout(tm),{passive:true});
document.addEventListener('touchstart',e=>{const a=e.target.closest&&e.target.closest('a[href]');if(a)pf(a)},{passive:true});
// 语言切换时带上当前的 #筛选状态
document.querySelectorAll('.lang a').forEach(a=>a.addEventListener('click',()=>{if(location.hash)a.href=a.getAttribute('href')+location.hash}));
})();

if(innerWidth<641)document.querySelectorAll('details.segd').forEach(d=>d.removeAttribute('open'));
// ---- 宏观页四层 Tab（M1）：#layer-N 锚点直达；切换用 replaceState 不跳动；左右方向键；从详情页回来恢复原 Tab 原位置
(function(){
 const bar=document.querySelector('[data-tabs]');if(!bar)return;
 const tabs=[...bar.querySelectorAll('[role=tab]')];const KEY='uc-macro-pos';
 function panelOf(el){return el&&el.closest?el.closest('.tabp'):null}
 function act(n,focus){tabs.forEach(t=>{const on=t.dataset.tab==String(n);t.classList.toggle('on',on);t.setAttribute('aria-selected',on?'true':'false');t.tabIndex=on?0:-1;
   const p=document.getElementById(t.getAttribute('aria-controls'));if(p)p.classList.toggle('on',on)});if(focus){const t=tabs.find(t=>t.dataset.tab==String(n));t&&t.focus()}
  if(window.ucBootCharts)setTimeout(()=>window.ucBootCharts(document.getElementById('layer-'+n)),30)}
 function cur(){const t=tabs.find(t=>t.classList.contains('on'));return t?t.dataset.tab:'1'}
 function go(hash,scroll){if(!hash)return false;const id=hash.slice(1);const el=document.getElementById(id);if(!el)return false;
  let n=null;const m=/^layer-(\d)$/.exec(id);if(m)n=m[1];else{const p=panelOf(el);if(p)n=p.id.split('-')[1]}
  if(!n)return false;act(n);if(scroll){if(m){const tw=document.querySelector('.tabwrap');window.scrollTo({top:Math.max(0,tw.getBoundingClientRect().top+scrollY-8)})}else setTimeout(()=>{el.scrollIntoView({block:'start'});flash(el)},40)}return true}
 function flash(el){if(!el)return;el.classList.remove('flash');void el.offsetWidth;el.classList.add('flash')}
 tabs.forEach((t,k)=>{t.addEventListener('click',e=>{e.preventDefault();act(t.dataset.tab);history.replaceState(null,'','#layer-'+t.dataset.tab)});
  t.addEventListener('keydown',e=>{if(e.key!=='ArrowRight'&&e.key!=='ArrowLeft')return;e.preventDefault();const j=(k+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
   act(tabs[j].dataset.tab,true);history.replaceState(null,'','#layer-'+tabs[j].dataset.tab)})});
 // 页面里指向其他 Tab 的链接（综合研判的层徽章、依据小芯片、#l2-levels 等）
 document.addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('a[href^="#"]');if(!a)return;const h=a.getAttribute('href');
  if(go(h,true)){e.preventDefault();history.replaceState(null,'',h)}});
 document.querySelectorAll('.segs a[data-tab],a.lb[data-tab]').forEach(a=>a.addEventListener('click',e=>{if(location.pathname===new URL(a.href).pathname){e.preventDefault();act(a.dataset.tab);
  history.replaceState(null,'','#layer-'+a.dataset.tab);const tw=document.querySelector('.tabwrap');window.scrollTo({top:Math.max(0,tw.getBoundingClientRect().top+scrollY-8),behavior:'smooth'})}}));
 window.addEventListener('hashchange',()=>go(location.hash,true));
 // 恢复位置：浏览器后退，或从本站指标详情页点面包屑回来
 let st=null;try{st=JSON.parse(sessionStorage.getItem(KEY)||'null')}catch(e){}
 const nav=(performance.getEntriesByType&&performance.getEntriesByType('navigation')[0]||{}).type;
 const fromDetail=/\/macro\/[a-z0-9_]+\/?$/.test(document.referrer.replace(/^https?:\/\/[^/]+/,'').replace(/^\/en/,''));
 if(!go(location.hash,false))act(st&&(nav==='back_forward'||fromDetail)?st.tab:'1');
 else if(location.hash&&!/^#layer-\d$/.test(location.hash))go(location.hash,true);
 if(st&&(nav==='back_forward'||fromDetail)&&st.tab===cur()&&st.y)setTimeout(()=>window.scrollTo(0,st.y),60);
 let tm=null;const save=()=>{try{sessionStorage.setItem(KEY,JSON.stringify({tab:cur(),y:Math.round(scrollY)}))}catch(e){}};
 window.addEventListener('scroll',()=>{clearTimeout(tm);tm=setTimeout(save,150)},{passive:true});window.addEventListener('pagehide',save);
 // 依据小芯片：跳到对应卡片并高亮 1 秒
 document.querySelectorAll('[data-hl]').forEach(a=>a.addEventListener('click',()=>setTimeout(()=>flash(document.getElementById(a.dataset.hl)),300)));
 // L1 二级锚点：滚动时当前分组高亮
 const an=[...document.querySelectorAll('.anch a')];if(an.length&&'IntersectionObserver' in window){const io=new IntersectionObserver(es=>{es.forEach(en=>{if(en.isIntersecting){
   an.forEach(a=>a.classList.toggle('on',a.dataset.anchor===en.target.id))}})},{rootMargin:'-150px 0px -65% 0px'});
  an.forEach(a=>{const t=document.getElementById(a.dataset.anchor);if(t)io.observe(t)})}
})();

// ---- 欢迎弹窗 / 版本更新弹窗（G1、G2）：本地存储记住看过哪一版；存储不可用就一律不弹
(function(){
 const meta=document.getElementById('ucg-meta');if(!meta)return;let M;try{M=JSON.parse(meta.textContent)}catch(e){return}
 const CUR=M.cur;let st=null;try{st=window.localStorage;st.getItem('_t')}catch(e){st=null}
 const get=k=>{try{return st?st.getItem(k):null}catch(e){return null}},set=(k,v)=>{try{st&&st.setItem(k,v)}catch(e){}};
 if(/\/changelog\/?$/.test(location.pathname))set('uo_log_seen',CUR);
 function dot(){const show=!!st&&!!get('uo_welcome_seen')&&get('uo_log_seen')!==CUR;document.querySelectorAll('.rdot').forEach(d=>d.hidden=!show)}
 dot();
 let open=null,back=null;
 function close(){if(!open)return;const o=open;open=null;o.remove();document.documentElement.classList.remove('ucg-on');if(o._done)o._done();if(back&&back.focus)back.focus();dot()}
 function show(id,done,filter){if(open)return;const tpl=document.getElementById(id);if(!tpl)return;back=document.activeElement;
  const wrap=document.createElement('div');wrap.className='ucg';wrap.setAttribute('role','dialog');wrap.setAttribute('aria-modal','true');wrap.setAttribute('aria-labelledby','ucg-t');
  const box=document.createElement('div');box.className='ucg-box';box.appendChild(tpl.content.cloneNode(true));
  if(filter){box.querySelectorAll('.ucg-v').forEach(v=>{if(!filter(v.dataset.v))v.remove()});const h=box.querySelector('.ucg-v h3');if(h)h.id='ucg-t'}
  const x=document.createElement('button');x.type='button';x.className='ucg-x';x.setAttribute('aria-label',document.documentElement.lang.startsWith('zh')?'关闭':'Close');x.textContent='×';box.prepend(x);
  wrap.appendChild(box);document.body.appendChild(wrap);document.documentElement.classList.add('ucg-on');open=wrap;wrap._done=done;
  wrap.addEventListener('click',e=>{if(e.target===wrap)close()});box.querySelectorAll('.ucg-ok,.ucg-x').forEach(b=>b.addEventListener('click',close));
  wrap.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();close();return}
   if(e.key==='Tab'){const f=[...box.querySelectorAll('a[href],button')];if(!f.length)return;const a=f[0],z=f[f.length-1];
    if(e.shiftKey&&document.activeElement===a){e.preventDefault();z.focus()}else if(!e.shiftKey&&document.activeElement===z){e.preventDefault();a.focus()}}});
  setTimeout(()=>{const b=box.querySelector('.ucg-ok')||x;b.focus()},30)}
 document.querySelectorAll('[data-guide]').forEach(b=>b.addEventListener('click',()=>{const n=document.getElementById('navtg');if(n)n.checked=false;
  show('ucg-welcome',()=>{set('uo_welcome_seen','1');if(!get('uo_last_seen_version'))set('uo_last_seen_version',CUR)})}));
 window.ucGuide=()=>show('ucg-welcome');
 const supp=/[?&](noguide=1|sharepreview)/.test(location.search)||window.self!==window.top||navigator.webdriver||
  /bot|crawl|spider|slurp|bingpreview|headless|lighthouse|facebookexternalhit|twitterbot|telegrambot|whatsapp/i.test(navigator.userAgent);
 if(!st||supp)return;
 function auto(){if(document.querySelector('.sc'))return;
  const welcomed=get('uo_welcome_seen'),last=get('uo_last_seen_version');
  if(!welcomed){show('ucg-welcome',()=>{set('uo_welcome_seen','1');set('uo_last_seen_version',CUR);set('uo_log_seen',CUR)});return}
  if(last!==CUR){const unseen=M.vers.filter(v=>v.n&&(!last||v.v>last)).map(v=>v.v).slice(0,3);
   if(unseen.length)show('ucg-update',()=>set('uo_last_seen_version',CUR),v=>unseen.includes(v));else set('uo_last_seen_version',CUR)}}
 if(document.readyState==='complete')setTimeout(auto,400);else window.addEventListener('load',()=>setTimeout(auto,400));
})();
// ---- 反馈 / 纠错（G10）：一键在 X 上 @ 站长，带上当前页面标题和链接
document.querySelectorAll('[data-feedback]').forEach(a=>{const zh=document.documentElement.lang.startsWith('zh');
 a.href='https://x.com/intent/post?text='+encodeURIComponent((zh?'@Uncle_Onchain 反馈：':'@Uncle_Onchain Feedback: ')+document.title.split(' · ')[0]+' ')+'&url='+encodeURIComponent(location.href.split('#')[0]);
 a.target='_blank';a.rel='noopener'});
// ---- 术语与标签解释（G7）：术语第一次出现加虚下划线；悬停（桌面）/ 点按（手机）显示一句话
(function(){
 const g=document.getElementById('uc-gloss');if(!g)return;let G;try{G=JSON.parse(g.textContent)}catch(e){return}
 const pop=document.createElement('div');pop.className='uc-pop';pop.hidden=true;pop.setAttribute('role','tooltip');document.body.appendChild(pop);
 function place(el,title,def){pop.innerHTML='';const b=document.createElement('b');b.textContent=title;const p=document.createElement('div');p.textContent=def;pop.append(b,p);pop.hidden=false;
  const r=el.getBoundingClientRect();const w=Math.min(300,innerWidth-16);pop.style.maxWidth=w+'px';let x=r.left+scrollX;if(x+w>scrollX+innerWidth-8)x=scrollX+innerWidth-8-w;
  pop.style.left=Math.max(scrollX+8,x)+'px';pop.style.top=(r.bottom+scrollY+6)+'px'}
 const hide=()=>{pop.hidden=true};
 const words=[];(G.terms||[]).forEach(t=>t.w.forEach(w=>words.push({w:w,d:t.d,k:t.w[0]})));words.sort((a,b)=>b.w.length-a.w.length);
 const root=document.querySelector('.mi');
 if(root&&words.length){const used=new Set();const skip='A,BUTTON,SCRIPT,STYLE,CODE,H1,TEXTAREA,INPUT,SUMMARY,TEMPLATE,SVG,TEXT,LABEL,NAV';
  const esc=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');const re=new RegExp('('+words.map(x=>esc(x.w)).join('|')+')');
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>{let p=n.parentElement;while(p&&p!==root){if(skip.includes(p.tagName)||p.classList.contains('term')||p.classList.contains('uc-chart')||p.classList.contains('chip')||p.classList.contains('grade'))return NodeFilter.FILTER_REJECT;p=p.parentElement}return re.test(n.nodeValue)?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_SKIP}});
  const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
  nodes.forEach(n=>{if(used.size>=words.length)return;const m=n.nodeValue.match(re);if(!m)return;const hit=words.find(x=>x.w===m[1]);if(!hit||used.has(hit.k))return;used.add(hit.k);
   const i=m.index,a=n.splitText(i);a.splitText(m[1].length);const sp=document.createElement('span');sp.className='term';sp.tabIndex=0;sp.dataset.def=hit.d;sp.dataset.t=m[1];
   a.parentNode.replaceChild(sp,a);sp.textContent=m[1]})}
 const tip=e=>{const t=e.target.closest&&e.target.closest('.term,[data-tag]');if(!t)return null;if(t.classList.contains('term'))return [t,t.dataset.t,t.dataset.def];
  const d=(G.tags||{})[t.dataset.tag];return d?[t,t.textContent,d]:null};
 document.addEventListener('mouseover',e=>{const x=tip(e);if(x)place(...x)},{passive:true});
 document.addEventListener('mouseout',e=>{if(tip(e))hide()},{passive:true});
 document.addEventListener('focusin',e=>{const x=tip(e);if(x)place(...x)});document.addEventListener('focusout',hide);
 document.addEventListener('click',e=>{const x=tip(e);if(x){if(x[0].closest('a'))e.preventDefault();place(...x)}else hide()});
})();
