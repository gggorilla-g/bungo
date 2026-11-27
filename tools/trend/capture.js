// capture.js — 動画を再生もダウンロードもせずに、ページの情報と「1秒ごとのコマ」を読む（2026-11-27 に動作を確認）
// 使い方（Claude in Chrome。youtube.com のページを開いたタブで）：
//   1. このファイルの中身を javascript_tool に渡す（window.META / window.CAP / window.CAPOFF ができる）
//   2. 数字だけ：        await META(['動画ID', ...])   → ID先頭5字 | 再生数 | 登録者 | 長さ | 公開日 | チャンネル | 題名
//   3. コマを見る：      await CAP('動画ID')           → 題名・説明などを返し、画面いっぱいにコマの一覧を出す（1枚＝9コマ、左から順に3枚まで）
//                        そのあと computer の screenshot で見る。見終わったら CAPOFF()
// しくみ：動画ページの HTML にあるプレーヤー情報（ytInitialPlayerResponse）を読み、シークバーのプレビュー用の小さな絵（storyboard）を並べる。
//         音は出ない。動画そのものは保存しない。絵も保存しない（見るだけ）。
// うまくいかなかった方法：/embed/<ID> を直接開く（エラー153）、youtube.com のページに埋め込む（エラー152-4）
window.PR = async (id) => {
  const html = await (await fetch('/watch?v=' + id)).text(); let pr = null; const seg = html.split('ytInitialPlayerResponse = ')[1] || ''; let k = -1;
  for (let n = 0; n < 40; n++) { k = seg.indexOf('};', k + 1); if (k < 0) break; try { pr = JSON.parse(seg.slice(0, k + 1)); break; } catch (e) { } }
  const subs = (html.match(/subscriberCountText.{0,300}?simpleText":"([^"]+)"/) || [])[1] || '?';
  return { pr, subs: subs.replace('チャンネル登録者数 ', '') }
};
window.META = async (ids) => {
  const rows = [];
  for (const id of ids) {
    try {
      const { pr, subs } = await PR(id); const vd = pr.videoDetails || {}, mf = (pr.microformat || {}).playerMicroformatRenderer || {};
      rows.push([id.slice(0, 5), vd.viewCount, subs, vd.lengthSeconds + 's', (mf.publishDate || '').slice(5, 10), (vd.author || '').slice(0, 16), (vd.title || '').replace(/#\S+/g, '').trim().slice(0, 44)].join(' | '));
    } catch (e) { rows.push(id.slice(0, 5) + ' err') }
  }
  return rows.join('\n')
};
window.CAPOFF = () => { document.getElementById('capbox')?.remove(); return 'off' };
window.CAP = async (id) => {
  const { pr, subs } = await PR(id); if (!pr) return 'player response not found';
  const vd = pr.videoDetails || {}, mf = (pr.microformat || {}).playerMicroformatRenderer || {};
  const spec = ((pr.storyboards || {}).playerStoryboardSpecRenderer || {}).spec || ''; const parts = spec.split('|'); let info = 'no storyboard'; CAPOFF();
  if (parts.length > 1) {
    const L = parts.length - 2; const lv = parts[parts.length - 1].split('#');
    const w = +lv[0], h = +lv[1], count = +lv[2], cols = +lv[3], rows = +lv[4], iv = +lv[5], name = lv[6], sigh = lv[7]; const sheets = Math.ceil(count / (cols * rows));
    const box = document.createElement('div'); box.id = 'capbox';
    box.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:2147483647;background:#111;display:flex;gap:6px;align-items:flex-start;overflow:hidden';
    for (let n = 0; n < Math.min(sheets, 3); n++) { const im = document.createElement('img'); im.src = parts[0].replace('$L', L).replace('$N', name.replace('$M', n)) + '&sigh=' + sigh; im.style.cssText = 'height:100vh;width:auto'; box.appendChild(im); }
    document.body.appendChild(box); info = 'storyboard ' + w + 'x' + h + ' frames ' + count + ' grid ' + cols + 'x' + rows + ' every ' + iv + 'ms sheets ' + sheets;
  }
  const desc = (vd.shortDescription || '').replace(/https?:\S+/g, '').replace(/[=&?]/g, ' ').replace(/\n+/g, ' / ').slice(0, 260);
  return ['title: ' + (vd.title || '').slice(0, 100), 'channel: ' + (vd.author || '') + ' (' + subs + ')', 'views: ' + vd.viewCount + ' length: ' + vd.lengthSeconds + 's published: ' + (mf.publishDate || '').slice(0, 10), info, 'desc: ' + desc].join('\n')
};
'ready'
