// 紙を折る題材の計算（ブラウザーと Node の両方で使う）。時間→折った回数→厚さ、字幕の展開
(function(root){
function make(spec){
  const TL=spec.timeline,K=TL.keys,CO=TL.coldOpenEnd,NE=TL.endN,P0=spec.paper.thicknessM,DUR=spec.output.durationSeconds;
  const REF={};for(const r of spec.references)REF[r.id]=r;
  // 折った回数（連続値）。冒頭のコールドオープンは最後の状態を見せる
  function nAt(t){if(t<CO)return NE;if(t<=K[0][0])return K[0][1];for(let i=0;i<K.length-1;i++){const a=K[i],b=K[i+1];if(t<=b[0])return a[1]+(b[1]-a[1])*(t-a[0])/(b[0]-a[0])}return K[K.length-1][1]}
  const nInt=t=>Math.floor(nAt(t)+1e-9);
  const thick=n=>P0*Math.pow(2,n);
  // 長さの表示：mm / cm / m / km
  function fmtLen(m){if(m<0.01)return(Math.round(m*10000)/10).toFixed(1)+'mm';if(m<1)return(Math.round(m*1000)/10).toFixed(1)+'cm';
    if(m<10)return(Math.round(m*100)/100).toFixed(2)+'m';if(m<100)return(Math.round(m*10)/10).toFixed(1)+'m';if(m<10000)return Math.round(m).toLocaleString('en-US')+'m';
    return Math.round(m/1000).toLocaleString('en-US')+'km'}
  const fmtNum=v=>typeof v==='number'?(Number.isInteger(v)?v.toLocaleString('en-US'):String(v)):String(v);
  const rec=REF.record?REF.record.value:12;
  function metric(b){switch(b.metric){case'thick':return fmtLen(thick(b.n));case'endN':return String(NE);case'restFromRecord':return String(NE-rec);default:throw new Error('未知のmetric: '+b.metric)}}
  function fill(str,c){return str.replace(/\{([^}]+)\}/g,(m,k)=>{
    if(k.startsWith('ref:')){const[id,f]=k.slice(4).split('.');const r=REF[id];if(!r)throw new Error('参照物がない: '+id);const v=r[f||'value'];if(v==null)throw new Error('参照物の欄がない: '+k);return (f==null||f==='value')?fmtNum(v):String(v)}
    const b=(c.bindings||{})[k];if(!b)throw new Error('bindingがない: {'+k+'} in '+str);return metric(b)})}
  function match(w,t,n){if(w.tMax!=null&&!(t<w.tMax))return false;if(w.tMin!=null&&!(t>=w.tMin))return false;if(w.nMin!=null&&n<w.nMin)return false;if(w.nMax!=null&&!(n<w.nMax))return false;return true}
  const notes=spec.notes||{};
  function captionAt(t){const n=nInt(t);for(const c of spec.captions)if(match(c.when,t,n))return{id:c.id,c1:c.main.map(x=>fill(x,c)),c2:(c.sub||[]).map(x=>fill(x,c)),note:c.note?notes[c.note]:undefined};
    throw new Error('字幕が見つからない t='+t)}
  return{spec,DUR,CO,NE,P0,REF,nAt,nInt,thick,fmtLen,captionAt,rec}}
if(typeof module!=='undefined')module.exports={make};else root.FOLD={make};
})(this);
