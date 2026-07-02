/* ===== Marketing Dog — BrandSkin adaptive theming (WCAG-AA by construction) =====
   Maps a brand's primary colour onto the app's CSS variables and keeps every
   token legible. Auto-skins to each brand's scanned palette; light + dark. */
(function(){
  const clamp01=x=>x<0?0:x>1?1:x, clmp=(x,a,b)=>x<a?a:x>b?b:x;
  const hexToRgb=h=>{h=String(h).trim().replace(/^#/,'');if(h.length===3)h=h.split('').map(c=>c+c).join('');const n=parseInt(h,16);return{r:(n>>16)&255,g:(n>>8)&255,b:n&255}};
  const rgbToHex=({r,g,b})=>'#'+[r,g,b].map(v=>Math.round(clmp(v,0,255)).toString(16).padStart(2,'0')).join('');
  const s2l=c=>{c/=255;return c<=0.04045?c/12.92:Math.pow((c+0.055)/1.055,2.4)};
  const l2s=c=>{const v=c<=0.0031308?c*12.92:1.055*Math.pow(c,1/2.4)-0.055;return clamp01(v)*255};
  const lum=x=>{const c=typeof x==='string'?hexToRgb(x):x;return 0.2126*s2l(c.r)+0.7152*s2l(c.g)+0.0722*s2l(c.b)};
  const contrast=(a,b)=>{const L1=lum(a),L2=lum(b),hi=Math.max(L1,L2),lo=Math.min(L1,L2);return(hi+0.05)/(lo+0.05)};
  const bestFg=bg=>contrast('#ffffff',bg)>=contrast('#000000',bg)?'#ffffff':'#000000';
  function rgbToOklab({r,g,b}){const lr=s2l(r),lg=s2l(g),lb=s2l(b);const l=0.4122214708*lr+0.5363325363*lg+0.0514459929*lb,m=0.2119034982*lr+0.6806995451*lg+0.1073969566*lb,s=0.0883024619*lr+0.2817188376*lg+0.6299787005*lb;const l_=Math.cbrt(l),m_=Math.cbrt(m),s_=Math.cbrt(s);return{L:0.2104542553*l_+0.7936177850*m_-0.0040720468*s_,a:1.9779984951*l_-2.4285922050*m_+0.4505937099*s_,b:0.0259040371*l_+0.7827717662*m_-0.8086757660*s_}}
  function oklabToRgb({L,a,b}){const l_=L+0.3963377774*a+0.2158037573*b,m_=L-0.1055613458*a-0.0638541728*b,s_=L-0.0894841775*a-1.2914855480*b;const l=l_**3,m=m_**3,s=s_**3;return{r:l2s(4.0767416621*l-3.3077115913*m+0.2309699292*s),g:l2s(-1.2684380046*l+2.6097574011*m-0.3413193965*s),b:l2s(-0.0041960863*l-0.7034186147*m+1.7076147010*s)}}
  const toOklch=rgb=>{const{L,a,b}=rgbToOklab(rgb);return{L,C:Math.hypot(a,b),h:Math.atan2(b,a)}};
  const oklchHex=({L,C,h})=>rgbToHex(oklabToRgb({L,a:C*Math.cos(h),b:C*Math.sin(h)}));
  const hexOklch=h=>toOklch(hexToRgb(h));
  const withL=(hex,L,cs=1)=>{const o=hexOklch(hex);return oklchHex({L:clamp01(L),C:o.C*cs,h:o.h})};
  function ensure(fg,bg,t){if(contrast(fg,bg)>=t)return fg;const d=lum(bg)<0.5?1:-1,o=hexOklch(fg);let best=fg,bc=contrast(fg,bg);for(let i=1;i<=120;i++){const k=i/120,L=clamp01(o.L+d*k),cand=oklchHex({L,C:o.C*Math.max(0.15,1-k*0.7),h:o.h}),c=contrast(cand,bg);if(c>bc){bc=c;best=cand}if(c>=t)return cand}const bw=bestFg(bg);return contrast(bw,bg)>bc?bw:best}
  function buildTheme(p){const ph=hexOklch(p).h,nu=(L,C=0.008)=>oklchHex({L,C,h:ph});
    const dBg=nu(0.16,0.012);let dA=withL(p,Math.max(0.74,hexOklch(p).L));dA=ensure(dA,dBg,3);
    const dark={bg:dBg,bg2:nu(0.195,0.012),panel:nu(0.215,0.014),panel2:nu(0.255,0.014),line:nu(0.315,0.01),ink:ensure(nu(0.965,0.004),dBg,7),mute:ensure(nu(0.7,0.012),dBg,4.5),accent:dA,accentInk:ensure(bestFg(dA),dA,4.5),good:ensure('#34d399',dBg,3),warn:ensure('#fbbf24',dBg,3),danger:ensure('#fb7185',dBg,3)};
    const lBg=nu(0.99,0.004);let lA=withL(p,Math.min(0.56,hexOklch(p).L));lA=ensure(lA,lBg,3);
    const light={bg:lBg,bg2:nu(0.972,0.005),panel:'#ffffff',panel2:nu(0.965,0.006),line:nu(0.9,0.012),ink:ensure(nu(0.24,0.02),lBg,7),mute:ensure(nu(0.52,0.02),lBg,4.5),accent:lA,accentInk:ensure(bestFg(lA),lA,4.5),good:ensure('#15803d',lBg,3),warn:ensure('#b45309',lBg,3),danger:ensure('#dc2626',lBg,3)};
    return{light,dark}}

  let MODE=localStorage.getItem('md_mode')||'light', OVERRIDE=null, LASTKEY='';
  const DOG='#E8912B';
  const isHex=c=>/^#?[0-9a-fA-F]{6}$/.test(String(c||'').replace('#',''));
  const norm=c=>{c=String(c);return c[0]==='#'?c:'#'+c};
  function brandPrimary(){try{const b=(typeof state!=='undefined'&&state)?state.brand:null;if(!b)return null;const k=(b.profile&&b.profile.brand_kit)||{};let c=(k.colors&&k.colors[0])||(b.scrape&&b.scrape.colors&&b.scrape.colors[0]);return isHex(c)?norm(c):null;}catch(e){return null}}
  function apply(primary){
    if(!isHex(primary))primary=DOG; primary=norm(primary);
    const t=buildTheme(primary)[MODE], R=document.documentElement.style, S=(k,v)=>R.setProperty(k,v);
    S('--bg',t.bg);S('--bg2',t.bg2);S('--panel',t.panel);S('--panel2',t.panel2);S('--line',t.line);
    S('--txt',t.ink);S('--mut',ensure(t.mute,MODE==='dark'?t.panel:t.bg,4.5));S('--yel',t.accent);S('--yelInk',t.accentInk);
    const yelBg=withL(t.accent,MODE==='dark'?0.27:0.93,0.7);S('--yelBg',yelBg);S('--yelD',ensure(t.accent,yelBg,4.5));
    S('--grn',t.good);S('--grnBg',withL(t.good,MODE==='dark'?0.27:0.93,0.6));S('--grnInk',ensure(bestFg(t.good),t.good,4.5));
    S('--warn',t.warn);S('--err',t.danger);
    document.documentElement.dataset.mode=MODE;
    const aa=document.getElementById('mdAA');
    if(aa){const ok=contrast(t.ink,t.bg)>=4.5&&contrast(t.accentInk,t.accent)>=4.5;aa.textContent=ok?'WCAG AA ✓':'check';aa.style.background=ok?'var(--grn)':'var(--err)';aa.style.color=ok?'var(--grnInk)':'#fff';}
    const ci=document.getElementById('mdColor');if(ci&&isHex(primary))ci.value=primary;
  }
  function esc2(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
  function brandLogo(){try{const b=(typeof state!=='undefined'&&state)?state.brand:null;if(!b)return null;const k=(b.profile&&b.profile.brand_kit)||{};if(k.logo)return '/workspaces/'+(b.grp?b.grp+'/':'')+b.slug+'/'+k.logo;if(b.scrape&&b.scrape.logo)return b.scrape.logo;return null;}catch(e){return null;}}
  function updateIdentity(){const el=document.querySelector('#shell aside .logo');if(!el)return;let b=null;try{b=(typeof state!=='undefined'&&state)?state.brand:null;}catch(e){}
    if(b&&b.name){const lg=brandLogo();el.innerHTML=(lg?'<img src="'+lg+'" alt="" referrerpolicy="no-referrer" onerror="this.style.display=\'none\'" style="width:26px;height:26px;border-radius:7px;object-fit:contain;background:var(--panel);border:1px solid var(--line)">':'<span class="dot">🐕</span>')+' <span style="max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block;vertical-align:middle">'+esc2(b.name)+'</span>';}
    else{el.innerHTML='<span class="dot">🐕</span> Marketing Dog';}}
  let PREVIEW=null, LASTBRAND='__init__';
  function reskin(){apply(PREVIEW||OVERRIDE||brandPrimary()||DOG);updateIdentity();}
  window.mdReskin=reskin;
  window.mdPreview=function(h){PREVIEW=h||null;LASTKEY='';reskin();};
  window.mdPreviewReset=function(){PREVIEW=null;LASTKEY='';reskin();};
  setInterval(function(){let b=null;try{b=(typeof state!=='undefined'&&state)?state.brand:null;}catch(e){}var bid=b?b.id:'dash';if(bid!==LASTBRAND){LASTBRAND=bid;PREVIEW=null;}const p=brandPrimary();const key=(PREVIEW||'')+'|'+(OVERRIDE||'')+'|'+MODE+'|'+bid+'|'+(p||'dog');if(key!==LASTKEY){LASTKEY=key;reskin();}},500);

  function segState(){document.querySelectorAll('#mdAppear .seg button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.m===MODE));}
  function mount(){
    if(document.getElementById('mdAppear'))return;
    const w=document.createElement('div');w.id='mdAppear';
    w.innerHTML='<button class="fab" aria-label="Appearance settings" aria-expanded="false">🎨</button>'+
      '<div class="pop" role="dialog" aria-label="Appearance"><h4>Appearance <span class="aa" id="mdAA">WCAG AA ✓</span></h4>'+
      '<div class="seg" role="group" aria-label="Colour mode"><button data-m="light">☀️ Light</button><button data-m="dark">🌙 Dark</button></div>'+
      '<label style="font-size:12px;color:var(--mut);font-weight:600">Brand accent</label>'+
      '<div style="display:flex;gap:8px;align-items:center;margin-top:4px"><input type="color" id="mdColor" value="#E8912B" aria-label="Brand accent colour" style="width:42px;height:34px;padding:0;border:1px solid var(--line);border-radius:8px;background:none;cursor:pointer"><button class="sm ghost" id="mdAuto" style="margin:0">Use brand colours</button></div>'+
      '<p class="sub" style="margin:10px 0 0;font-size:11.5px">The UI adapts to each brand’s scanned colours — always kept readable.</p></div>';
    document.body.appendChild(w);
    const fab=w.querySelector('.fab');
    fab.addEventListener('click',()=>{const o=w.classList.toggle('open');fab.setAttribute('aria-expanded',o);});
    w.querySelectorAll('.seg button').forEach(b=>b.addEventListener('click',()=>{MODE=b.dataset.m;localStorage.setItem('md_mode',MODE);segState();LASTKEY='';reskin();}));
    w.querySelector('#mdColor').addEventListener('input',e=>{OVERRIDE=e.target.value;LASTKEY='';reskin();});
    w.querySelector('#mdAuto').addEventListener('click',()=>{OVERRIDE=null;LASTKEY='';reskin();});
    segState();reskin();
  }
  if(document.readyState!=='loading')mount();else document.addEventListener('DOMContentLoaded',mount);
  reskin();
})();
