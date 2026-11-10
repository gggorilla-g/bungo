# ビッグフェイスの〇〇（BIG FACE / LITTLE STORIES）

2026-11-10 ゲンタさん「新企画」。オリジナル3Dショートアニメ、シーズン1は全10話（各30〜45秒）。
仕様の元は SPEC.txt（統合クリエイティブ・制作マスター仕様書、ゲンタさん作）。台本・演出・3D・音はすべてこれに合わせる。

## いまの段階
- Phase 1（映像の試作）：EP.01 冒頭「せまいドア」約8.6秒。cg/bf.js（three.js、セルルック）→ make_test.py（文字と音）
- 投稿先のチャンネルは未定（ゲンタさんに確認）

## 作り方
- CG：node bigface/cg/render.js jobs.json（jobs = [{scene:"ep01_test", d, fps:30, w:1080, h:1920, out}]）
- 仕上げ：python3 bigface/make_test.py <コマのフォルダ> <出力.mp4>（-14 LUFS、AAC 48kHz）
- フォント：bigface/fonts（Zen Maru Gothic / Zen Kaku Gothic New / Zen Old Mincho、SIL OFL。google/fonts から取得）
- 声：VOICEVOX の仮の声（雨晴はう、ゆっくり・抑揚ひかえめ）。声は Phase 2 で決める
