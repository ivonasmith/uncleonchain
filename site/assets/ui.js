
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
