"""冒頭に「結末の一瞬」を差しこむ（11/23 分析：伸びた放物線は 視聴を継続 74.8%、新作は 42〜56%。冒頭で何が起きるかを見せる）。
使い方: python3 tools/teaser.py in.mp4 out.mp4 開始秒 [長さ=1.0]
  開始秒〜長さ の区間（いちばん見栄えのする瞬間）を先頭に置き、そのあと本編を最初から流す。最後と最初が同じ絵になり、ループもしやすい"""
import subprocess, sys
src, out, at = sys.argv[1], sys.argv[2], float(sys.argv[3]); ln = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
# 同じ入力を2回開く（1本の入力を split すると、結末を待つ間に本編の生フレームを溜めこみ、メモリ不足で落ちる）
f = (f"[0:v]setpts=PTS-STARTPTS,fade=t=out:st={ln - .12}:d=0.12:color=white[v0];"
     f"[0:a]asetpts=PTS-STARTPTS,afade=t=out:st={ln - .15}:d=0.15[a0];"
     f"[1:v]setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.12:color=white[v1];[1:a]asetpts=PTS-STARTPTS[a1];"
     f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(at), "-t", str(ln), "-i", src, "-i", src, "-filter_complex", f, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", out], check=True)
print("teaser:", out)
