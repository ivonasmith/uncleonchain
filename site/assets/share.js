
(function(){
const H2C=['/assets/vendor/html2canvas.min.js','https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js','https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js'];
const ZH=document.documentElement.lang.startsWith('zh');
function toast(t){let e=document.querySelector('.toast');if(!e){e=document.createElement('div');e.className='toast';document.body.appendChild(e)}
 e.textContent=t;e.classList.add('on');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('on'),2600)}
function one(u){return new Promise((ok,no)=>{const s=document.createElement('script');s.src=u;s.onload=ok;s.onerror=()=>{s.remove();no()};document.head.appendChild(s)})}
async function lib(){if(window.html2canvas)return;for(const u of H2C){try{await one(u);if(window.html2canvas)return}catch(e){}}throw new Error(ZH?'截图库加载失败，请检查网络':'Could not load the screenshot library')}
window.ucShare=async function(o){
 toast(ZH?'正在生成长图…':'Rendering image…');
 const st=document.createElement('div');st.className='sc';
 st.innerHTML='<div class="sc-hd"><img src="/assets/avatar-96.png" alt=""><div><b>'+(ZH?'链上大叔研究台':'Uncle Onchain')+'</b><i>uncleonchain.com · @Uncle_Onchain</i></div>'+
  '<div class="sc-date">'+(o.date||'')+'</div></div><div class="sc-title">'+o.title+'</div>'+(o.sub?'<div class="sc-sub">'+o.sub+'</div>':'')+o.html+
  '<div class="sc-ft"><b>uncleonchain.com</b><span>@Uncle_Onchain</span><span style="margin-left:auto">'+(o.src||(ZH?'只给数据 · 不构成投资建议':'Data only · not investment advice'))+'</span></div>';
 document.body.appendChild(st);
 if(location.search.includes('sharepreview')){st.style.left='0';st.style.zIndex='999';return}
 try{await lib();await new Promise(r=>setTimeout(r,120));
  const c=await html2canvas(st,{scale:2,backgroundColor:'#05070c',useCORS:true,logging:false});
  const a=document.createElement('a');a.download=o.file||'uncleonchain.png';a.href=c.toDataURL('image/png');document.body.appendChild(a);a.click();a.remove();
  toast(ZH?'长图已下载 ✓ 直接发推':'Image downloaded ✓');
 }catch(e){toast((ZH?'生成失败：':'Failed: ')+e.message)}finally{st.remove()}
};
window.ucToast=toast;
})();
