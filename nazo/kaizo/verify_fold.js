// 字幕の照合（紙を折る題材）：全コマで字幕を展開し、比較の主張を計算と突き合わせる。問題があれば終了コード1
const fs=require('fs'),{make}=require('./fold_calc.js');
const specPath=process.argv[2]||'specs/fold42.json',spec=JSON.parse(fs.readFileSync(specPath,'utf8')),C=make(spec);
const fps=spec.output.fps,N=Math.round(C.DUR*fps),seen=new Map(),err=[],warn=[],ok=[];
// 時間割：単調、30秒で終わる、最後は endN
const K=spec.timeline.keys;for(let i=1;i<K.length;i++){if(!(K[i][0]>K[i-1][0]))err.push(`時間割の時刻が増えていない: ${K[i-1][0]}→${K[i][0]}`);if(K[i][1]<K[i-1][1])err.push(`回数が減っている: ${K[i-1][1]}→${K[i][1]}`)}
if(K[K.length-1][0]!==C.DUR)err.push('時間割が'+C.DUR+'秒で終わっていない');if(K[K.length-1][1]!==C.NE)err.push('最後の回数が endN と違う');
for(let i=0;i<N;i++){const t=i/fps;let c;try{c=C.captionAt(t)}catch(e){err.push(`f${i} ${e.message}`);continue}if(!c.c1.length)err.push(`f${i} 大字幕が空`);
  if(!seen.has(c.id))seen.set(c.id,{first:i,last:i,c});else seen.get(c.id).last=i}
for(const c of spec.captions)if(!seen.has(c.id))warn.push(`字幕 ${c.id} は一度も出ない`);
// 字幕の数字が、その字幕が出ている間の画面の回数と食い違わないか（「n回で」の n と、表示中の回数）
for(const[id,s]of seen){const m=s.c.c1.join('').match(/^(\d+)回[で。]/);if(!m)continue;const want=+m[1];
  for(let i=s.first;i<=s.last;i++){const n=C.nInt(i/fps);if(i/fps>=spec.timeline.coldOpenEnd&&n<want){err.push(`${id}: f${i} 画面は${n}回なのに字幕は${want}回`);break}}}
// 比較の主張：n回目で初めて超える
for(const c of spec.captions)for(const ch of(c.checks||[])){const r=C.REF[ch.ref];if(!r){err.push(`${c.id}: 参照物 ${ch.ref} がない`);continue}
  const v=C.thick(ch.n),p=C.thick(ch.n-1),lim=r.valueM;const good=v>lim&&!(p>lim);
  (good?ok:err).push(`${good?'OK':'NG'} ${c.id}: ${ch.n}回 ${C.fmtLen(v)} > ${r.label} ${r.value.toLocaleString('en-US')}${r.unit}、${ch.n-1}回 ${C.fmtLen(p)} は未満`)}
for(const r of spec.references)if(r.kind==='external-fact'&&!r.sourceUrl)warn.push(`出典未記入: ${r.label}`);
console.log('字幕の一覧（区間は秒）');for(const[id,s]of[...seen].sort((a,b)=>a[1].first-b[1].first))console.log(`  ${(s.first/fps).toFixed(2)}-${((s.last+1)/fps).toFixed(2)} ${id}: ${s.c.c1.join('')} / ${s.c.c2.join('')}${s.c.note?' / '+s.c.note:''}`);
console.log('比較の照合');ok.forEach(x=>console.log('  '+x));
if(warn.length){console.log('要確認');warn.forEach(x=>console.log('  '+x))}
if(err.length){console.log('NG');err.forEach(x=>console.log('  '+x));process.exit(1)}console.log('結果: NG 0件');
