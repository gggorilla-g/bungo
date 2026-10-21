"""学習の記録から、約1分のダイジェスト動画を作る（ずんだもんの声とテロップつき）。
python gamelab/make_digest.py gamelab/history.json out.mp4"""
import json, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import game, render

FPS = 30
SR = 24000
B = "build_game"
os.makedirs(B, exist_ok=True)

# 罠ごとの、ずんだもんのせりふ（日本語・英語・声のスタイル）。罠の場所は x（px）
EVENTS = {
    "落ちる天井": (game.THWOMP_X, "天井が落ちてきたのだ！？", "The ceiling fell on me?!", 7),
    "隠しトゲ": (game.HIDDEN[0][0], "床からトゲが出たのだ！聞いてないのだ！", "Spikes from the floor?! Nobody told me!", 7),
    "偽ゴール": (game.FAKE_GOAL_X, "ゴールなのだ！……偽物なのだーっ！", "GOAL! ...It's a fake!!", 7),
    "ノコギリ": (42 * game.T, "ノコギリが動いてるのだ……", "The saw is moving...", 3),
    "天井トゲ": (52 * game.T, "ジャンプしたら刺さるのだ", "Don't jump here!", 3),
}
CRUMBLE_X = 128 * game.T


def tts(text, style, out):
    from voicevox_core.blocking import Synthesizer, Onnxruntime, OpenJtalk, VoiceModelFile
    global _SYN
    if "_SYN" not in globals():
        A = "vv_assets"; ORT = "1.17.3"
        ort = Onnxruntime.load_once(filename=f"{A}/voicevox_onnxruntime-linux-x64-{ORT}/lib/libvoicevox_onnxruntime.so.{ORT}")
        _SYN = Synthesizer(ort, OpenJtalk(f"{A}/open_jtalk_dic_utf_8-1.11"))
        with VoiceModelFile.open(f"{A}/0.vvm") as m:
            _SYN.load_voice_model(m)
    aq = _SYN.create_audio_query(text, style_id=style)
    aq.speed_scale = 1.15
    open(out, "wb").write(_SYN.synthesis(aq, style_id=style))
    with wave.open(out) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def blip(freq=520, dur=0.07, vol=0.18):
    t = np.arange(int(SR * dur)) / SR
    return (np.sin(2 * np.pi * freq * t * (1 - t * 4)) * np.exp(-t * 40) * vol).astype(np.float32)


def fanfare():
    out = np.zeros(int(SR * 1.6), np.float32)
    for i, f in enumerate((523, 659, 784, 1047)):
        t = np.arange(int(SR * 0.5)) / SR
        s = (np.sign(np.sin(2 * np.pi * f * t)) * 0.08 * np.exp(-t * 3)).astype(np.float32)
        o = int(SR * 0.12 * i)
        out[o:o + len(s)] += s
    return out


def telop(im, ja, en):
    d = ImageDraw.Draw(im)
    size = 54
    while True:
        f1 = render.font(size)
        bb = d.textbbox((0, 0), ja, font=f1)
        w = bb[2] - bb[0]
        if w <= render.W - 120 or size <= 30:
            break
        size -= 2
    f2 = render.font(30)
    x0 = (render.W - w) // 2
    d.rectangle([x0 - 24, 150, x0 + w + 24, 230], fill=(255, 230, 60))
    d.text((render.W // 2, 190), ja, font=f1, fill=(20, 20, 20), anchor="mm")
    d.text((render.W // 2, 262), en, font=f2, fill=(255, 255, 255), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))


def title_card(im, ja, en):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 230, render.W, 470], fill=(0, 0, 0))
    d.text((render.W // 2, 320), ja, font=render.font(70), fill=(255, 230, 60), anchor="mm")
    d.text((render.W // 2, 410), en, font=render.font(34), fill=(255, 255, 255), anchor="mm")


def main(hpath, out):
    hist = json.load(open(hpath))
    first = {}
    for h in hist:
        for c in h["causes"]:
            first.setdefault(c, h["gen"])
    win = next((h["gen"] for h in hist if h["won"]), None)
    assert win, "まだクリアしていない"
    by = {h["gen"]: h for h in hist}
    # 見せる場面：1世代目 → 罠に初めて出会った世代（出会った順）→ 早送り → クリアした世代
    plan = [("intro", 1)]
    for c, g in sorted(first.items(), key=lambda kv: kv[1]):
        if c in EVENTS and g > 1:
            plan.append(("event:" + c, g))
    plan.append(("montage", None))
    plan.append(("win", win))

    frames_path = f"{B}/frames.raw"
    fo = open(frames_path, "wb")
    audio = []          # (秒, 波形)
    nframe = 0
    graves = []

    def emit(im):
        nonlocal nframe
        fo.write(im.tobytes()); nframe += 1

    def play(gen, t0, t1, speed, lines=(), title=None, mark_deaths=True, cam_lead=True, xlines=()):
        """世代genの上位の挑戦を、tick t0〜t1 を speed倍で再生"""
        h = by[gen]
        sim = render.simulate(h["genomes"][:40])
        t1 = min(t1, len(sim) - 1)
        best = h["best_x"]
        dead_seen = set()
        cam = None
        tt = t0
        start_frame = nframe
        line_q = list(lines)
        xq = list(xlines)
        cur = None
        while tt <= t1:
            t = int(tt)
            row = sim[t]
            lead = render.leader(row)
            target = max(0, min(game.WPX - 896, lead[0] - 300))
            cam = target if cam is None else cam + (target - cam) * 0.15
            for i, r in enumerate(row):
                if not r[2] and i not in dead_seen:
                    dead_seen.add(i)
                    graves.append((r[0] + game.AW / 2, r[1] + game.AH / 2))
                    if mark_deaths and len(dead_seen) < 25:
                        audio.append((nframe / FPS, blip(400 + 20 * (i % 10))))
            im, d, lead = render.draw_frame(row, t, cam, graves[-400:])
            im = im.crop((0, 200, 896, 704)).resize((render.W, render.H), Image.LANCZOS)
            d = ImageDraw.Draw(im)
            lost = h.get("lost", game_pop() - h["won"])
            frac = sum(1 for r in row if not r[2]) / len(row)
            deaths = h["deaths_total"] - lost + int(lost * frac)
            render.hud(im, d, gen, max(deaths, 0), best, lead[0])
            sec = (nframe - start_frame) / FPS
            while line_q and line_q[0][0] <= sec:
                at, ja, en, st = line_q.pop(0)
                wav = tts(ja, st, f"{B}/v{len(audio)}.wav")
                audio.append((nframe / FPS, wav))
                cur = (ja, en, nframe + max(int(len(wav) / SR * FPS) + 12, 45))
            if xq and lead[0] >= xq[0][0] and not (cur and nframe < cur[2]):
                _, ja, en, st = xq.pop(0)
                line_q.insert(0, (0, ja, en, st))
                at, ja, en, st = line_q.pop(0)
                wav = tts(ja, st, f"{B}/v{len(audio)}.wav")
                audio.append((nframe / FPS, wav))
                cur = (ja, en, nframe + max(int(len(wav) / SR * FPS) + 12, 45))
            if cur and nframe < cur[2]:
                telop(im, cur[0], cur[1])
            if any(r[3] for r in row) and gen == win:
                ImageDraw.Draw(im).text((render.W // 2, 400), "CLEAR!", font=render.font(120), fill=(255, 230, 60),
                                        anchor="mm", stroke_width=8, stroke_fill=(0, 0, 0))
            if title and sec < title[2]:
                title_card(im, title[0], title[1])
            emit(im)
            tt += speed
        return sim

    def tick_at(sim, x):
        for t, row in enumerate(sim):
            if render.leader(row)[0] >= x:
                return t
        return len(sim) - 1

    for kind, gen in plan:
        if kind == "intro":
            play(1, 0, 400, 1.0,
                 lines=[(0.3, "AIのボクが、AIの作った鬼畜ゲーをクリアするのだ！", "I'm an AI. I'll beat a game another AI made!", 1),
                        (4.6, "……全員死んだのだ", "...Everyone died.", 3)],
                 title=("AIずんだもん vs 鬼畜ゲー", "AI vs a brutal game made by AI", 3.6))
        elif kind.startswith("event:"):
            c = kind.split(":")[1]
            x, ja, en, st = EVENTS[c]
            sim = render.simulate(by[gen]["genomes"][:40])
            t = tick_at(sim, x - 380)
            play(gen, t, t + 200, 1.0, lines=[(0.8, ja, en, st)])
        elif kind == "montage":
            gens = [h["gen"] for h in hist if h["gen"] < win]
            pick = gens[len(gens) // 4::max(1, len(gens) // 8)][:6]
            for i, g in enumerate(pick):
                sim = render.simulate(by[g]["genomes"][:40])
                t = max(0, len(sim) - 90)
                ln = [(0.1, "もう何回死んだかわからないのだ", "I've lost count of my deaths.", 3)] if i == 1 else []
                play(g, t, t + 80, 2.0, lines=ln, mark_deaths=False)
        elif kind == "win":
            sim = render.simulate(by[gen]["genomes"][:40])
            end = next((t for t, row in enumerate(sim) if any(r[3] for r in row)), len(sim) - 1)
            t0 = tick_at(sim, CRUMBLE_X - 600)
            t0 = tick_at(sim, game.THWOMP_X - 500)
            play(gen, t0, end - 20, 2.0,
                 xlines=[(game.THWOMP_X - 300, "天井が落ちたら、いったん下がるのだ", "Wait for the ceiling to drop...", 3),
                         (CRUMBLE_X - 200, "床が崩れる前に、走り抜けるのだ！", "Run before the floor crumbles!", 7),
                         (148 * game.T, "ノコギリの間を、すり抜けるのだ", "Slip between the saws!", 3),
                         (game.HIDDEN[1][0] - 250, "このトゲも、もう知ってるのだ", "I know this trap now.", 1),
                         (game.FAKE_GOAL2_X - 200, "偽ゴールには、もうだまされないのだ", "Not fooled by fake goals anymore!", 7)])
            # クリアの瞬間を等速で、ファンファーレとせりふ
            audio.append((nframe / FPS, fanfare()))
            play(gen, end - 20, end + 60, 1.0,
                 lines=[(0.5, "やったのだー！クリアしたのだ！", "I did it!! I beat it!", 1)], mark_deaths=False)
            # しめ：死亡数の大写し
            h = by[gen]
            last = Image.new("RGB", (render.W, render.H), render.BG)
            d = ImageDraw.Draw(last)
            d.text((render.W // 2, 400), f"GEN {gen}", font=render.font(70), fill=(255, 255, 255), anchor="mm")
            d.text((render.W // 2, 520), f"DEATHS {h['deaths_total']:,}", font=render.font(110), fill=(255, 110, 110), anchor="mm")
            wav = tts("次はもっと鬼畜なのを持ってくるのだ", 7, f"{B}/vend.wav")
            audio.append((nframe / FPS + 0.3, wav))
            n = int((len(wav) / SR + 1.5) * FPS)
            for k in range(n):
                im = last.copy()
                telop(im, "次はもっと鬼畜なのを持ってくるのだ", "Bring me something harder next time.")
                emit(im)
    fo.close()
    dur = nframe / FPS
    mix = np.zeros(int(SR * (dur + 1)), np.float32)
    for at, w in audio:
        o = int(at * SR)
        mix[o:o + len(w)] += w[:len(mix) - o]
    mix = np.clip(mix, -1, 1)
    with wave.open(f"{B}/mix.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{render.W}x{render.H}",
                    "-r", str(FPS), "-i", frames_path, "-i", f"{B}/mix.wav", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-shortest", out], check=True)
    os.remove(frames_path)
    print(f"{out}: {dur:.1f}秒")


def game_pop():
    import evolve
    return evolve.POP


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
