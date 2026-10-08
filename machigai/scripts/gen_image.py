"""元絵の生成（Codex担当）。
優先順：
 1) Codex CLI の $imagegen（ChatGPTプランのログイン or OPENAI_API_KEY）
 2) OPENAI_API_KEY があれば Images API を直接呼ぶ（Codexが失敗した時の保険）
 3) --local 指定時のみ、試験用の仮イラスト（本番では使わない）
差分を作りやすい絵にするため、プロンプトで「独立した小物が多い・背景はベタ」を指定する。"""
import base64, zlib, glob, json, os, shutil, subprocess, sys, time, urllib.request

STYLE = (
    "Flat vector illustration for a spot-the-difference puzzle. "
    "Landscape 3:2. Bright, clean colors. Solid flat color areas, no texture, no gradients, no text, no letters, no logos. "
    "Many separate, clearly outlined small and medium objects (at least 25) spread across the whole picture, "
    "each standing on a plain background area, not overlapping each other. "
    "No people's faces in close-up. No real brands or famous characters."
)

def prompt_for(theme):
    return f"Scene: {theme}. {STYLE}"

def via_codex(prompt, out_path):
    if not shutil.which("codex"):
        return False
    home = os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex"))
    before = set(glob.glob(f"{home}/generated_images/**/*.png", recursive=True))
    task = (f"$imagegen Generate exactly one image, size 1536x1024. Prompt: {prompt} "
            f"Save the final image as {os.path.abspath(out_path)} . Do not do anything else.")
    try:
        subprocess.run(["codex", "exec", "--skip-git-repo-check", "--full-auto", task],
                       check=True, timeout=600)
    except Exception as e:
        print("codex失敗:", e)
    if os.path.exists(out_path):
        return True
    after = set(glob.glob(f"{home}/generated_images/**/*.png", recursive=True)) - before
    if after:   # 指定先に保存されなかった場合は生成フォルダの最新を拾う
        shutil.copy(max(after, key=os.path.getmtime), out_path)
        return True
    return False

def via_api(prompt, out_path):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return False
    body = json.dumps({"model": os.environ.get("IMAGE_MODEL", "gpt-image-2"),
                       "prompt": prompt, "size": "1536x1024", "n": 1}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.load(r)["data"][0]
            open(out_path, "wb").write(base64.b64decode(d["b64_json"]))
            return True
        except Exception as e:
            print("API失敗:", e); time.sleep(10 * (i + 1))
    return False

def generate(theme, out_path, local=False):
    if local:
        sys.path.insert(0, os.path.dirname(__file__))
        from base_scene import scene
        scene(seed=zlib.crc32(theme.encode()) % 1000).save(out_path)
        return "local"
    p = prompt_for(theme)
    if via_codex(p, out_path):
        return "codex"
    if via_api(p, out_path):
        return "api"
    raise RuntimeError("画像を生成できませんでした")

if __name__ == "__main__":
    print(generate(sys.argv[1], sys.argv[2], local="--local" in sys.argv))
