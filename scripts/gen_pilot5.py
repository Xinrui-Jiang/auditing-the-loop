"""Generate the first 5 pilot clips with Seedance 1.5 Pro (480p, 9:16, 8 s, audio on) via OpenRouter."""
import os, json, time, hashlib, pathlib, sys, httpx
from dotenv import load_dotenv
ROOT = pathlib.Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)
H = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
BASE = "https://openrouter.ai/api/v1"
SHOTS = sys.argv[1:] or ["DB-16", "DB-35", "DB-38", "SB-01", "DB-60"]
rows = {json.loads(l)["shot_id"]: json.loads(l) for l in open(ROOT / "data/prompts/prompt_set_v2_30.jsonl")}
jobs = {}
for sid in SHOTS:
    r = rows[sid]
    body = {"model": "bytedance/seedance-1-5-pro", "prompt": r["prompt"], "duration": 8, "resolution": "480p", "aspect_ratio": "9:16", "generate_audio": True}
    j = httpx.post(f"{BASE}/videos", headers=H, json=body, timeout=120).raise_for_status().json()
    jobs[sid] = j; print("submitted", sid, j["id"], j.get("status"), flush=True)
t0 = time.time(); done = {}
while len(done) < len(jobs) and time.time() - t0 < 900:
    time.sleep(12)
    for sid, j in jobs.items():
        if sid in done: continue
        poll = j["polling_url"] if j["polling_url"].startswith("http") else "https://openrouter.ai" + j["polling_url"]
        p = httpx.get(poll, headers=H, timeout=60).json(); st = p.get("status")
        if st == "completed":
            url = (p.get("unsigned_urls") or [f"{BASE}/videos/{j['id']}/content?index=0"])[0]
            data = httpx.get(url, headers=H if "openrouter.ai" in url else {}, timeout=180, follow_redirects=True).content
            out = ROOT / "data/pilot_takes" / sid; out.mkdir(parents=True, exist_ok=True)
            fn = out / "attempt1_seedance480.mp4"; fn.write_bytes(data)
            g = httpx.get(f"{BASE}/generation?id={j['id']}", headers=H, timeout=60).json().get("data", {})
            meta = dict(shot_id=sid, model="bytedance/seedance-1-5-pro", resolution="480p", aspect_ratio="9:16", duration=8, job_id=j["id"], cost_usd=g.get("total_cost"), gen_model=g.get("model"), sha256=hashlib.sha256(data).hexdigest(), video=str(fn.relative_to(ROOT)), prompt=rows[sid]["prompt"], elapsed_s=round(time.time()-t0))
            (out / "attempt1_seedance480.json").write_text(json.dumps(meta, indent=1))
            done[sid] = meta; print("done", sid, len(data)//1024, "KB cost", g.get("total_cost"), f"{time.time()-t0:.0f}s", flush=True)
        elif st in {"failed", "cancelled", "expired"}:
            done[sid] = {"shot_id": sid, "error": p}; print("FAILED", sid, p, flush=True)
print("total cost", sum((m.get("cost_usd") or 0) for m in done.values()))
