"""間違い探しショートのナレーション（VOICEVOX:青山龍星）。
決まった短い文だけを読むので、読み間違いの心配がない言い回しに限定している。"""
import os, subprocess, wave
import numpy as np

A = os.path.join(os.path.dirname(__file__), "..", "..", "vv_assets")
ORT = "1.17.3"
VVM = "15.vvm"     # 青山龍星 を含むモデル
STYLE = 13         # 青山龍星 ノーマル
CREDIT = "VOICEVOX:青山龍星"
SR = 44100         # 動画側の音声と合わせる
NUM = {1: "ひとつ", 2: "ふたつ", 3: "みっつ", 4: "よっつ", 5: "いつつ", 6: "むっつ", 7: "ななつ"}
ORD = {1: "ひとつめ", 2: "ふたつめ", 3: "みっつめ", 4: "よっつめ", 5: "いつつめ", 6: "むっつめ", 7: "ななつめ"}

_syn = None


def _synth():
    global _syn
    if _syn is None:
        from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
        ort = Onnxruntime.load_once(filename=f"{A}/voicevox_onnxruntime-linux-x64-{ORT}/lib/libvoicevox_onnxruntime.so.{ORT}")
        _syn = Synthesizer(ort, OpenJtalk(f"{A}/open_jtalk_dic_utf_8-1.11"))
        with VoiceModelFile.open(f"{A}/{VVM}") as m:
            _syn.load_voice_model(m)
    return _syn


def say(text, speed=1.12):
    """文を読み上げ、44.1kHzモノラルのfloat配列で返す"""
    s = _synth()
    q = s.create_audio_query(text, style_id=STYLE)
    q.speed_scale = speed
    wav = s.synthesis(q, style_id=STYLE)
    tmp = "/tmp/_nar.wav"
    open(tmp, "wb").write(wav)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", tmp, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def lines(n, search):
    """場面ごとの台詞。数字はかなで書いて読みを固定する"""
    return {
        "intro": f"間違いは、{NUM[n]}。{search}秒で、見つけてください。",
        "last3": "あと、さんびょう。",
        "answer": "答え合わせです。",
        "each": [ORD[k] for k in range(1, n + 1)],
        "outro": "全部、見つけられましたか。チャンネル登録も、よろしくお願いします。",
    }
