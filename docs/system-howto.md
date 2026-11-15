# 自動投稿システムの作り方・指示の出し方（2026-11-15 時点）

## 全体
- コードは GitHub の gggorilla-g/bungo（1つのリポジトリで全チャンネル分）。
- 作業はクラウドの作業環境で Claude が行う（ゲンタさんのPCは使わない）。変更は毎回コミットして push する。
- 動画は「台本（JSON）→ 絵（Python の合成、または three.js の3DCG）→ 声（VOICEVOX）→ 音（効果音・BGMは自作の合成音）→ ffmpeg で mp4」の順で作る。
- 投稿は2通り。
  - YouTube Data API（videos.insert と thumbnails.set だけ使う）で予約投稿。
  - Claude がゲンタさんの Chrome で YouTube Studio を操作してアップロード（ビッグフェイスと、試作を即時公開するとき）。
- 記録は docs/video-ledger.md（プロジェクトの claude/video-ledger.md にも同じ内容）。

## チャンネルと作り方
| チャンネル | 中身 | 作るファイル | 台本 |
|---|---|---|---|
| ずんだもんの脳がとける雑学 | 動く間違い探し「どこちがう？」（3DCGの箱庭、ドライブ版） | nazo/machigai3d.py（絵は nazo/cg/scene.js） | nazo/shorts/mach3d_XXX.json |
| ずんだもんの脳がとける雑学 | 雑学ショート（写真＋動き） | nazo/short3.py | nazo/shorts/<ID>.json |
| ずんだもんの妄想科学 | 3DCGの妄想科学ショート | nazo/moso3d.py（絵は nazo/cg/） | nazo/shorts/<ID>.json |
| ザ・ビッグフェイス | セリフなし3Dショートアニメ | bigface/cg/bf.js（絵）＋ bigface/make_ep0N.py（音・文字） | bigface/cg/ep0N_time.json（カットの秒数） |
| ホー博士 | 11/13 で制作停止（自動の仕組みも止めた） | nazo/main.py ほか | — |
| Make It Work 3D（旧 今晩の百物語、UCBx3enM2p7aBROCU_EafuAw、@makeitwork3d） | 英語の仕組み系3Dショート（身近な物を問題→解決で改造）。11/15 に名前・説明・アイコン・バナーを英語に変更し、怪談の動画15本とショート8本を非公開にした（削除はしていない） | nazo/kaizo3d.py（絵は nazo/kaizo/） | nazo/shorts/kaizo_<ID>.json |
| ずんだもんの妄想科学（改造ショート） | 身近な物を問題→解決で改造していく3D（試作中） | nazo/kaizo3d.py | nazo/shorts/kaizo_<ID>.json |

- 3DCG は three.js をヘッドレスの Chromium で1コマずつ描いて画像にし、Python で文字・声・音を重ねる。
- 重い書き出しは GitHub Actions でも回せる（例：.github/workflows/mach3d.yml に台本IDを渡す）。

## ずんだもんの声（どこで入れているか）
- 声は VOICEVOX（voicevox_core）をサーバーなしでプログラムから直接呼んでいる。
- 声を出す関数：src/render.py の tts()。話者の切り替えは set_voice(vvm, style, speed, pitch, intonation)。
  - ずんだもん＝モデル 0.vvm のスタイル 3。間違い探しは speed 1.27・intonation 1.6・pitch 0.04（ハイテンション版）。
  - ビッグフェイスのタイトル読みだけ雨晴はう（0.vvm のスタイル 10）。
- VOICEVOX 本体と辞書は src/setup_voicevox.py が vv_assets/ に入れる。
- 読み間違い対策：読み上げる全文をまず「読みの関門」に通す（src/yomi.py / src/yomi_gate.py）。
  関門を通っていない文は tts() がエラーにして読まない。直した読みは state/yomi_learned.json に溜まる。
  - 例：python nazo/machigai3d.py check mach3d_008 → 合格すると nazo/state/mach3d_yomi_mach3d_008.json
- クレジットは動画内と説明欄に「VOICEVOX:ずんだもん」（ビッグフェイスは「タイトルの声：VOICEVOX:雨晴はう」）。

## 指示の出し方（Claude へ）
- 基本は一言でよい。例：
  - 「ビッグフェイス5話目」→ 案を出す → 作る → 動画を送る → 「公開して」で公開。
  - 「脳溶けの次」→ 次の型を提案 → 「はい」で試作。
  - 直しはそのまま書く：「唐突すぎる」「Tシャツの白い四角いらない」「芽が出た理由が謎」。
- Claude が勝手にしないこと：公開（新しい型・アニメは見てもらってから）、削除、コメント返信、購入、アカウント・チャンネル作成。
- 確認は1問ずつテキストで聞く。絵文字なし。観測と憶測は分けて書く。
- 決めたことは bigface/DECISIONS.md（プロジェクトの claude/bigface-decisions.md）と各 RULES に残す。

## よく使うコマンド（Claude 用メモ）
- 間違い探し：python nazo/machigai3d.py check <ID> → python nazo/machigai3d.py build <ID> → output/<ID>.mp4
- ビッグフェイス：node bigface/cg/render.js <設定.json>（コマ書き出し）→ python bigface/make_ep0N.py <コマのフォルダ> output/bigface_ep0N.mp4
- ブラウザから上げられるのは 10MB まで。超えたら ffmpeg の2パスで再圧縮してから上げる。
