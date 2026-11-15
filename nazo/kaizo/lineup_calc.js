// 並べて比べる3D（大きさ比べ）の計算：並び・時間割・字幕の文字をすべてここから出す（ブラウザーと Node の両方）
// spec: { lang: "ja"|"en", output:{fps,durationSeconds}, intro, outro, title:{ja,en}, items:[{id,name:{ja,en},m,ft?,kind,source,shape}] }
(function(root){
const FT=3.28084;
// 形の高さ（段の高さの合計）と幅（ブースターを含む）
function shapeSize(it){const s=it.shape||{};
  if(s.type==='person')return{h:s.h||1.7,w:.5};
  if(s.type==='rocket'){let h=0,w=0;for(const g of s.stages){h+=g.h;w=Math.max(w,g.d,g.d1||0)}
    if(s.boosters){const b=s.boosters;w=Math.max(w,(s.stages[0].d)+2*b.d)}return{h,w}}
  throw new Error('未知の形: '+s.type+'（'+it.id+'）')}
function make(spec){
  const lang=spec.lang||'ja',L=o=>typeof o==='string'?o:(o[lang]||o.ja||o.en);
  const items=spec.items.map(it=>Object.assign({},it,shapeSize(it)));
  // 並び：小さい順に左から。間は大きい方の高さに比例
  let x=0;items.forEach((it,i)=>{if(i>0){const p=items[i-1];x+=(p.w+it.w)/2+Math.max(.8,.22*it.h)}it.x=x});
  const fps=spec.output.fps,DUR=spec.output.durationSeconds,IN=spec.intro||1.6,OUT=spec.outro||4.5,N=items.length;
  const SLOT=(DUR-IN-OUT)/N;if(!(SLOT>=2.2))throw new Error('1つあたりの時間が短すぎる: '+SLOT.toFixed(2)+'秒');
  items.forEach((it,i)=>{it.t0=IN+i*SLOT;it.t1=it.t0+SLOT});
  const T_OUT=IN+N*SLOT;
  // 表示する数字（m は出典の値。ft は出典にあればそれ、無ければ換算）
  const fmtNum=(v,d)=>{const r=Math.round(v*Math.pow(10,d))/Math.pow(10,d);return r.toLocaleString('en-US',{minimumFractionDigits:0,maximumFractionDigits:d})};
  function valueText(it){const d=it.m<10?1:(it.m<100&&it.m%1!==0?1:0),mT=fmtNum(it.m,d)+' m';
    if(lang==='en'){const ft=it.ft!=null?it.ft:it.m*FT;return mT+' ('+fmtNum(ft,ft<10?1:0)+' ft)'}
    return (it.kind==='scene-assumption'?'約':'')+fmtNum(it.m,d)+'m'}
  const nameText=it=>L(it.name);
  // いまの注目（どの物を見せているか）
  function focusAt(t){if(t<IN)return{i:0,k:1};if(t>=T_OUT)return{i:N-1,k:1,out:Math.min(1,(t-T_OUT)/1.6)};
    const i=Math.min(N-1,Math.floor((t-IN)/SLOT)),u=(t-items[i].t0)/SLOT;return{i,k:Math.min(1,u/.32)}}
  function captionAt(t){const f=focusAt(t);if(t<IN)return{c1:L(spec.title),c2:''};
    if(f.out!=null&&f.out>0)return{c1:L(spec.endLine||spec.title),c2:''};
    const it=items[f.i];return{c1:nameText(it),c2:valueText(it)}}
  return{spec,lang,items,N,IN,OUT,SLOT,DUR,T_OUT,fps,FT,valueText,nameText,focusAt,captionAt,L}}
if(typeof module!=='undefined')module.exports={make,shapeSize};else root.LINEUP={make,shapeSize};
})(this);
