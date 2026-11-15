// 字幕の照合：spec の字幕を全コマで展開し、数字・比較の主張を計算と突き合わせる
// 使い方: node verify.js [specs/jump.json]   問題があれば終了コード1
const fs=require('fs'),path=require('path'),{make}=require('./calc.js');
const specPath=process.argv[2]||'specs/jump.json',spec=JSON.parse(fs.readFileSync(specPath,'utf8'));
const out=[],err=[],warn=[];let C;
try{C=make(spec)}catch(e){console.log('NG 時間割: '+e.message);process.exit(1)}
const fps=spec.output.fps,N=Math.round(C.DUR*fps),seen=new Map();
// 1. 全コマで字幕が必ず出るか、展開に失敗しないか
const fe=new Map();for(let i=0;i<N;i++){const t=i/fps;let c;try{c=C.captionAt(t)}catch(e){const k=e.message;if(!fe.has(k))fe.set(k,[i,i]);else fe.get(k)[1]=i;continue}
  if(!c.c1.length)err.push(`f${i} 大字幕が空`);if(!seen.has(c.id))seen.set(c.id,{first:i,last:i,c});else seen.get(c.id).last=i}
for(const[k,[f0,f1]]of fe)err.push(`f${f0}-f${f1}（${(f0/fps).toFixed(2)}-${((f1+1)/fps).toFixed(2)}秒） 字幕の展開に失敗: ${k}`);
for(const c of spec.captions)if(!seen.has(c.id))warn.push(`字幕 ${c.id} は一度も出ない`);
// 1b. 最後の区間が空中のまま終わるか（着地して止まった絵で終わらないか）
{const L=C.SEG[C.SEG.length-1];if(L.type==='flight'){const st=C.stateAt(C.DUR-1e-6);if(st.y<=0)err.push(`最後の区間（${L.n}回目）が30秒より前に着地して、地面で止まったまま終わる`)}}
// 2. 比較の主張
const val=(ch)=>C.metric(ch.metric,ch.n);
for(const c of spec.captions)for(const ch of(c.checks||[])){
  const r=ch.ref?C.REF[ch.ref]:null;if(ch.ref&&!r){err.push(`${c.id}: 参照物 ${ch.ref} がない`);continue}
  const v=val(ch),prev=ch.n>1?C.metric(ch.metric,ch.n-1):-Infinity,lim=r?r.value:ch.threshold;
  let ok,desc;
  if(ch.type==='exceeds'){ok=v>lim;desc=`${ch.n}回目 ${C.fmt(v)} > ${lim}`}
  else if(ch.type==='firstExceeds'){ok=v>lim&&!(prev>lim);desc=`${ch.n}回目 ${C.fmt(v)} > ${lim}、${ch.n-1}回目 ${C.fmt(prev)} は未満`}
  else if(ch.type==='firstReach'){ok=v>=lim&&prev<lim;desc=`${ch.n}回目 ${C.fmt(v)} >= ${lim}、${ch.n-1}回目 ${C.fmt(prev)} は未満`}
  else{err.push(`${c.id}: 未知のcheck ${ch.type}`);continue}
  (ok?out:err).push(`${ok?'OK':'NG'} ${c.id}: ${desc}${r?'（'+r.label+'）':''}`)}
// 3. 出典のない外部事実と、目安の言い回し
for(const r of spec.references)if(r.kind==='external-fact'&&!r.sourceUrl)warn.push(`出典未記入: ${r.label} ${r.value}${r.unit}`);
for(const c of spec.captions)if(c.approx)warn.push(`目安の言い回し（人が確認）: ${c.id}「${(c.sub||[]).join('')}」 ${c.approx}`);
// 4. 字幕の一覧（出る区間と展開後の文）
console.log('字幕の一覧（区間は秒）');
for(const[id,s]of[...seen].sort((a,b)=>a[1].first-b[1].first))console.log(`  ${(s.first/fps).toFixed(2)}-${((s.last+1)/fps).toFixed(2)} ${id}: ${s.c.c1.join('')} / ${s.c.c2.join('')}${s.c.note?' / '+s.c.note:''}`);
console.log('比較の照合');out.forEach(x=>console.log('  '+x));
if(warn.length){console.log('要確認');warn.forEach(x=>console.log('  '+x))}
if(err.length){console.log('NG');err.forEach(x=>console.log('  '+x));process.exit(1)}
console.log('結果: NG 0件');
