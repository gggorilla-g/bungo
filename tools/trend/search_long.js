// search_long.js — YouTube の検索結果から、長尺（ショートではない動画）を再生数の多い順に読む（2026-11-28 に書いた。まだ実際の検索結果では試していない）
//   持ち主 11/28「長尺がキモ…再現性とやれることで」→ 探す係で長尺も探す
// 使い方（Claude in Chrome）：
//   1. https://www.youtube.com/results?search_query=<語>&sp=<絞りこみ> を開く
//        EgQIBBgD … 今月＋4〜20分 ／ EgQIBBgC … 今月＋20分以上（長尺は伸びるのに日数がかかるので「今月」）
//   2. このファイルの中身を javascript_tool にそのまま渡す
// 出力：再生数 / 公開からの時間 / 長さ / 動画ID（6文字目のあとに空白。つなげて使う） / チャンネル / 題名
// 注意：出力は約1,000字で切られる。URL や「a=b」の形を出力に入れると止められる。ショートの欄（ytm-shorts-lockup-view-model）は読まない
await new Promise(r => setTimeout(r, 3000)); window.scrollTo(0, 6000); await new Promise(r => setTimeout(r, 2200));
const pv = s => { const m = (s || '').match(/([\d.,]+)\s*(万|億)?\s*回/); if (!m) return 0; return parseFloat(m[1].replace(/,/g, '')) * (m[2] == '万' ? 1e4 : m[2] == '億' ? 1e8 : 1) };
const ph = s => { const m = (s || '').match(/(\d+)\s*(分|時間|日|週間|か月|年)前/); if (!m) return 'h?'; const n = +m[1]; return Math.round(m[2] == '分' ? n / 60 : m[2] == '時間' ? n : m[2] == '日' ? n * 24 : m[2] == '週間' ? n * 168 : m[2] == 'か月' ? n * 720 : n * 8760) + 'h' };
const seen = new Set();
[...document.querySelectorAll('ytd-video-renderer')].map(e => {
  const a = e.querySelector('a#video-title, a#thumbnail'); const href = a?.getAttribute('href') || ''; const id = (href.split('v=')[1] || '').split('&')[0];
  const meta = [...e.querySelectorAll('#metadata-line span, .inline-metadata-item')].map(x => x.innerText.trim());
  const views = meta.find(x => /回視聴/.test(x)) || ''; const age = meta.find(x => /前/.test(x)) || '';
  const len = (e.querySelector('ytd-thumbnail-overlay-time-status-renderer, badge-shape .badge-shape-wiz__text, .yt-badge-shape__text')?.innerText || '').trim();
  const ch = (e.querySelector('ytd-channel-name #text, ytd-channel-name a')?.innerText || '').trim().slice(0, 16);
  const t = (e.querySelector('#video-title')?.innerText || '').trim().slice(0, 60);
  return { id, v: pv(views), h: ph(age), len, ch, t }
}).filter(o => o.id && o.v && !seen.has(o.id) && seen.add(o.id)).sort((a, b) => b.v - a.v).slice(0, 8)
  .map(o => [o.v, o.h, o.len, o.id.slice(0, 6) + ' ' + o.id.slice(6), o.ch, o.t].join(' / ')).join('\n')
