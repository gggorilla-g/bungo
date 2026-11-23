#!/usr/bin/env python3
"""remux.py <spec.json> — 書き出し済みの絵（build_ballsim/<id>_v.mp4）と音（<id>.wav）から、output/<id>.mp4 だけ作り直す。
spec の post_hue・post_pitch を足したあと、絵を作り直さずに反映するため（数十秒で終わる）"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import simkit
sp = json.load(open(sys.argv[1])); i = sp["id"]; raw, wv = f"build_ballsim/{i}_v.mp4", f"build_ballsim/{i}.wav"
if not (os.path.exists(raw) and os.path.exists(wv)): sys.exit(f"絵か音がない: {i}（sims.py で作り直す）")
simkit.mux(sp, raw, wv, f"output/{i}.mp4"); simkit.kit(sp); print("作り直し:", i)
