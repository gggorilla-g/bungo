// 大きさ比べの照合：並び順・出典・形の高さと数値の一致・ft の換算・字幕の展開を確かめる
// 使い方: node verify_lineup.js specs/xxx.json   NG があれば終了コード1
const fs=require('fs'),{make}=require('./lineup_calc.js');
const spec=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const err=[],warn=[],ok=[];let C;
try{C=make(spec)}catch(e){console.log('NG 時間割・形: '+e.message);process.exit(1)}
const its=C.items;
its.forEach((it,i)=>{
  if(i>0&&!(it.m>its[i-1].m))err.push(`並び順：${it.id}（${it.m}）が前の ${its[i-1].id}（${its[i-1].m}）以下`);
  if(it.kind==='external-fact'&&!(it.source&&it.source.url&&it.source.checkedAt))err.push(`出典なし：${it.id}`);
  if(it.kind!=='external-fact'&&it.kind!=='scene-assumption')err.push(`kind が不明：${it.id}`);
  if(Math.abs(it.h-it.m)/it.m>.015)err.push(`形の高さ ${it.h.toFixed(2)}m と数値 ${it.m}m が合わない：${it.id}`);else ok.push(`形の高さ一致 ${it.id} ${it.h.toFixed(2)}≒${it.m}`);
  if(it.ft!=null&&Math.abs(it.m*C.FT-it.ft)/it.ft>.01)err.push(`m と ft が合わない：${it.id} ${it.m}m=${(it.m*C.FT).toFixed(1)}ft / 出典 ${it.ft}ft`);
  for(const l of['ja','en'])if(!it.name||!it.name[l])err.push(`名前（${l}）なし：${it.id}`);
});
// 全コマで字幕が出るか
const N=Math.round(C.DUR*C.fps);const seen=new Map();
for(let f=0;f<N;f++){const t=f/C.fps;let c;try{c=C.captionAt(t)}catch(e){err.push(`f${f} 字幕の展開に失敗：${e.message}`);break}
  if(!c.c1)err.push(`f${f} 字幕が空`);const k=c.c1+' / '+c.c2;if(!seen.has(k))seen.set(k,t)}
if(!spec.post||!spec.post.title||!spec.post.desc)err.push('post（題名・説明）がない');
for(const it of its)if(it.source&&spec.post&&!spec.post.desc.includes(it.source.url))warn.push(`説明欄に出典URLがない：${it.id}`);
console.log(`1つあたり ${C.SLOT.toFixed(2)}秒、${C.N}個、全体 ${C.DUR}秒`);
console.log('字幕の一覧');for(const[k,t]of seen)console.log(`  ${t.toFixed(2)} ${k}`);
console.log('照合');ok.forEach(x=>console.log('  OK '+x));
if(warn.length){console.log('要確認');warn.forEach(x=>console.log('  '+x))}
if(err.length){console.log('NG');err.forEach(x=>console.log('  '+x));process.exit(1)}
console.log('結果: NG 0件');
