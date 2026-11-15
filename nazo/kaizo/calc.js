// 計算の一本化：時間割・物理・字幕の数字はすべてここから出す（ブラウザーと Node の両方で使う）
(function(root){
function make(spec){
  const P=spec.physics,G=P.gravityMps2,H0=P.baseHeightM,M=P.multiplier,PUSH=P.pushDistanceM,DUR=spec.output.durationSeconds;
  const hN=n=>H0*Math.pow(M,n-1),v0N=n=>Math.sqrt(2*G*hN(n)),airN=n=>2*v0N(n)/G,gN=n=>hN(n)/PUSH,kmhN=n=>v0N(n)*3.6;
  // 区間内の再生速度の時間割 [[u,倍率],...]
  function speedAt(p,u){if(u<=p[0][0])return p[0][1];for(let i=0;i<p.length-1;i++){const a=p[i],b=p[i+1];if(u<=b[0])return a[1]+(b[1]-a[1])*(u-a[0])/(b[0]-a[0])}return p[p.length-1][1]}
  function tauAt(p,u){let tau=0;for(let i=0;i<p.length-1;i++){const a=p[i],b=p[i+1];if(u<=a[0])return tau;const ue=Math.min(u,b[0]),se=a[1]+(b[1]-a[1])*(ue-a[0])/(b[0]-a[0]);tau+=(a[1]+se)/2*(ue-a[0])}
    const l=p[p.length-1];if(u>l[0])tau+=l[1]*(u-l[0]);return tau}
  // 時間割を組む
  const SEG=[];let t=0;
  for(const q of spec.timeline){const o=Object.assign({},q);
    if(o.type==='contact'){o.dur=o.durationSeconds}
    else if(o.fillToEnd){o.dur=DUR-t;if(!(o.dur>0))throw new Error('時間割が'+DUR+'秒をこえた（最後の区間が負）');if(o.speedProfile){o.prof=o.speedProfile;o.speed=o.speed||o.prof[0][1]}else o.speed=o.speed||1}
    else if(o.speedProfile){const p=o.speedProfile,last=p[p.length-1][0];o.prof=p;o.speed=o.speed||p[0][1];o.dur=last+(airN(o.n)-tauAt(p,last))/p[p.length-1][1]}
    else{o.speed=o.speed||1;o.dur=airN(o.n)/o.speed}
    if(o.cameraTransitionSeconds)o.T=o.cameraTransitionSeconds;
    o.t0=t;t+=o.dur;o.t1=t;SEG.push(o)}
  if(Math.abs(t-DUR)>1e-9)throw new Error('時間割の合計が'+t.toFixed(3)+'秒（'+DUR+'秒であるべき）');
  const segAt=tt=>{for(const s of SEG)if(tt<s.t1)return s;return SEG[SEG.length-1]};
  const segOf=(type,n)=>SEG.find(s=>s.type===type&&s.n===n);
  function stateAt(tt){const s=segAt(tt),u=tt-s.t0,st={seg:s,type:s.type,n:s.n,u,y:0,vy:0,tau:0,speed:1,k:0};
    if(s.type==='flight'){const v0=v0N(s.n),tau=s.prof?tauAt(s.prof,u):u*s.speed;st.tau=tau;st.y=Math.max(0,v0*tau-.5*G*tau*tau);st.vy=v0-G*tau;st.speed=s.prof?speedAt(s.prof,u):s.speed}
    else{st.k=u/s.dur}
    st.dispN=(s.type==='contact')?(s.crouch?s.next:s.n):s.n;return st}
  // 参照物
  const REF={};for(const r of spec.references)REF[r.id]=r;
  // 字幕に差しこむ数値
  const firstOver=v=>{let n=1;while(hN(n)<v&&n<200)n++;return n};
  function metric(name,n){switch(name){case'heightM':return hN(n);case'heightCm':return hN(n)*100;case'airSeconds':return airN(n);case'pushG':return gN(n);case'landingKmh':return kmhN(n);
    case'pushCm':return PUSH*100;case'firstNOver':return firstOver(n);default:throw new Error('未知のmetric: '+name)}}
  const fmt=(v,f)=>{if(f==='integer')return String(Math.round(v));if(f==='oneDecimal')return(Math.round(v*10)/10).toFixed(1);
    return Math.round(v*100)/100>=1000?Math.round(v).toLocaleString('en-US'):String(Math.round(v*100)/100)};
  // {名前} を値に置きかえる。名前は caption.bindings か ref:<id>.<field>
  function fill(str,c){return str.replace(/\{([^}]+)\}/g,(m,k)=>{
    if(k.startsWith('ref:')){const[id,f]=k.slice(4).split('.');const r=REF[id];if(!r)throw new Error('参照物がない: '+id);const v=r[f||'value'];if(v==null)throw new Error('参照物の欄がない: '+k);return (f==null||f==='value')&&typeof v==='number'?fmt(v):String(v)}
    const b=(c.bindings||{})[k];if(!b)throw new Error('bindingがない: {'+k+'} in '+str);return fmt(metric(b.metric,b.n!=null?b.n:b.value),b.format)})}
  const match=(w,st)=>{const s=st.seg,n=st.dispN;
    if(w.any)return w.any.some(x=>match(x,st));
    if(w.n!=null&&n!==w.n)return false;if(w.nMin!=null&&n<w.nMin)return false;
    if(w.segType&&s.type!==w.segType)return false;if(w.segN!=null&&s.n!==w.segN)return false;if(w.crouch!=null&&!!s.crouch!==w.crouch)return false;
    if(w.uBelow!=null&&!(st.u<w.uBelow))return false;return true};
  const notes=spec.notes||{};
  function captionAt(tt,st){st=st||stateAt(tt);for(const c of spec.captions)if(match(c.when,st)){
      return{id:c.id,c1:c.main.map(x=>fill(x,c)),c2:(c.sub||[]).map(x=>fill(x,c)),note:c.note?(notes[c.note]!=null?notes[c.note]:fill(c.note,c)):undefined}}
    throw new Error('字幕が見つからない t='+tt)}
  return{spec,G,H0,M,PUSH,DUR,hN,v0N,airN,gN,kmhN,SEG,segAt,segOf,stateAt,REF,metric,fmt,fill,captionAt}}
if(typeof module!=='undefined')module.exports={make};else root.CALC={make};
})(this);
