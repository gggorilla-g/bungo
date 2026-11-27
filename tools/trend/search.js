// search.js — YouTube の検索結果から、今週のショートを再生数の多い順に読む（2026-11-27 に動作を確認）
// 使い方（Claude in Chrome）：
//   1. https://www.youtube.com/results?search_query=<語>&sp=EgQIAxgB を開く（sp=EgQIAxgB は「今週」＋「4分未満」）
//   2. このファイルの中身を javascript_tool にそのまま渡す
// 出力：再生数 / 公開からの時間 / 動画ID（6文字目のあとに空白を入れてある。つなげて使う） / 題名
// 注意：出力は約1,000字で切られる。URL や「a=b」の形を出力に入れると止められる
await new Promise(r => setTimeout(r, 3000)); window.scrollTo(0, 6000); await new Promise(r => setTimeout(r, 2200));
const pv = s => { const m = (s || '').match(/([\d.,]+)\s*(万|億)?\s*回/); if (!m) return 0; return parseFloat(m[1].replace(/,/g, '')) * (m[2] == '万' ? 1e4 : m[2] == '億' ? 1e8 : 1) };
const ph = s => { const m = (s || '').match(/(\d+)\s*(分|時間|日|週間|か月)前/); if (!m) return 999; const n = +m[1]; return m[2] == '分' ? n / 60 : m[2] == '時間' ? n : m[2] == '日' ? n * 24 : m[2] == '週間' ? n * 168 : n * 720 };
const seen = new Set();
[...document.querySelectorAll('ytm-shorts-lockup-view-model')].map(e => {
  const p = e.innerText.split(/\n+/).map(x => x.trim()).filter(Boolean).filter(x => x != '新着');
  const a = e.querySelector('a[href*="/shorts/"]'); const id = (a?.getAttribute('href') || '').split('/shorts/')[1] || '';
  const meta = p.find(x => /回視聴/.test(x)) || ''; return { id, t: (p[0] || '').slice(0, 70), v: pv(meta), h: ph(meta) }
}).filter(o => o.v && !seen.has(o.id) && seen.add(o.id)).sort((a, b) => b.v - a.v).slice(0, 8)
  .map(o => [o.v, Math.round(o.h) + 'h', o.id.slice(0, 6) + ' ' + o.id.slice(6), o.t].join(' / ')).join('\n')
