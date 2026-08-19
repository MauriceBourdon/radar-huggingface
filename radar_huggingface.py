import datetime as dt
import json
import os
import re
from typing import Dict, List, Optional

import requests

HF_API = "https://huggingface.co/api"
WINDOW_DAYS = 30
CARD_LIMIT = 5000
SEARCH_LIMIT = 50
FAMILIES = [
    "MiniMax H3", "LTX-2.5", "LTX 2.5", "Wan video", "Qwen Image",
    "Flux image", "SeedVR", "video LoRA", "camera LoRA", "ComfyUI video",
]
WATCH_AUTHORS = ["lightx2v", "EllaPriest45", "Comfy-Org"]


def headers() -> Dict[str, str]:
    h = {"User-Agent": "radar-huggingface/1.0"}
    token = os.environ.get("HF_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get_json(path: str, params=None):
    r = requests.get(f"{HF_API}{path}", headers=headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def load_feed() -> Dict:
    try:
        with open("feed.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"generated_at": None, "window": "rolling-30d", "models": []}


def parse_dt(value: Optional[str]):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def search_models(query: str) -> List[Dict]:
    try:
        data = get_json("/models", {"search": query, "sort": "lastModified", "direction": -1, "limit": SEARCH_LIMIT, "full": "true"})
        return data if isinstance(data, list) else []
    except requests.RequestException:
        return []


def author_models(author: str) -> List[Dict]:
    try:
        data = get_json("/models", {"author": author, "sort": "lastModified", "direction": -1, "limit": SEARCH_LIMIT, "full": "true"})
        return data if isinstance(data, list) else []
    except requests.RequestException:
        return []


def model_info(model_id: str) -> Dict:
    return get_json(f"/models/{model_id}")


def model_card(model_id: str) -> Optional[str]:
    for name in ("README.md", "readme.md"):
        url = f"https://huggingface.co/{model_id}/resolve/main/{name}"
        r = requests.get(url, headers=headers(), timeout=30)
        if r.status_code == 200:
            text = r.text.strip()
            return text[:CARD_LIMIT] if text else None
    return None


def classify(model: Dict, card: str = "") -> str:
    text = " ".join([model.get("id") or "", " ".join(model.get("tags") or []), card or ""]).lower()
    if "lora" in text:
        return "LoRA"
    if "gguf" in text or "quant" in text or "int8" in text or "fp8" in text or "nvfp4" in text:
        return "quantization"
    if "adapter" in text or "controlnet" in text:
        return "adapter"
    if any(x in text for x in ["vae", "upscaler", "latent", "encoder"]):
        return "utility"
    return "base-model"


def files_summary(info: Dict) -> List[Dict]:
    out = []
    for sibling in info.get("siblings") or []:
        name = sibling.get("rfilename") or ""
        if re.search(r"\.(safetensors|gguf|bin|pt|pth)$", name, re.I):
            out.append({"name": name, "size": sibling.get("size")})
    return out[:100]


def discover() -> Dict[str, Dict]:
    found = {}
    for q in FAMILIES:
        for model in search_models(q):
            if model.get("id"):
                found[model["id"]] = model
    for author in WATCH_AUTHORS:
        for model in author_models(author):
            if model.get("id"):
                found[model["id"]] = model
    return found


def build_feed() -> Dict:
    now = dt.datetime.now(dt.timezone.utc)
    now_iso = now.isoformat()
    old_feed = load_feed()
    old_by_id = {m.get("id"): m for m in old_feed.get("models", []) if m.get("id")}
    discovered = discover()
    refreshed = {}
    events = []

    for model_id, summary in discovered.items():
        old = old_by_id.get(model_id)
        modified = summary.get("lastModified")
        changed = old is None or modified != old.get("lastModified")
        if changed:
            try:
                info = model_info(model_id)
            except requests.RequestException:
                info = summary
            card = model_card(model_id)
            item = {
                "id": model_id,
                "url": f"https://huggingface.co/{model_id}",
                "author": model_id.split("/", 1)[0] if "/" in model_id else None,
                "createdAt": info.get("createdAt") or summary.get("createdAt"),
                "lastModified": info.get("lastModified") or modified,
                "likes": info.get("likes"),
                "downloads": info.get("downloads"),
                "pipeline_tag": info.get("pipeline_tag"),
                "library_name": info.get("library_name"),
                "tags": info.get("tags") or [],
                "card_excerpt": card,
                "files": files_summary(info),
                "kind": classify(info, card or ""),
                "first_seen_at": old.get("first_seen_at") if old else now_iso,
                "last_seen_at": now_iso,
                "activity_history": list(old.get("activity_history", [])) if old else [],
            }
            event = {"detected_at": now_iso, "type": "NEW" if old is None else "UPDATE", "lastModified": item.get("lastModified")}
            item["activity_history"].append(event)
            item["activity_history"] = item["activity_history"][-100:]
            refreshed[model_id] = item
            events.append({"id": model_id, "type": event["type"]})
        else:
            copy = dict(old)
            copy["last_seen_at"] = now_iso
            refreshed[model_id] = copy

    cutoff = now - dt.timedelta(days=WINDOW_DAYS)
    models = []
    for old in old_feed.get("models", []):
        model_id = old.get("id")
        item = refreshed.pop(model_id, None) or old
        last_seen = parse_dt(item.get("last_seen_at"))
        if last_seen and last_seen >= cutoff:
            models.append(item)
    models.extend(refreshed.values())
    models.sort(key=lambda x: x.get("lastModified") or "", reverse=True)
    return {"generated_at": now_iso, "window": "rolling-30d", "current_run_events": events, "models": models}


def write_outputs(feed: Dict) -> None:
    with open("feed.json", "w", encoding="utf-8") as f:
        json.dump(feed, f, indent=2, ensure_ascii=False)
    by_id = {m["id"]: m for m in feed.get("models", [])}
    lines = ["# Radar Hugging Face", "", f"Généré : {feed.get('generated_at')}", "", "## Delta du run", ""]
    for event in feed.get("current_run_events", []):
        m = by_id.get(event["id"], {})
        lines.append(f"- [{event['type']}] {event['id']} — {m.get('kind')} — {m.get('url')}")
    with open("feed.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open("summary.txt", "w", encoding="utf-8") as f:
        f.write(f"Radar Hugging Face mis à jour\nModels suivis : {len(feed.get('models', []))}\nÉvénements du run : {len(feed.get('current_run_events', []))}\n")


def main() -> None:
    feed = build_feed()
    write_outputs(feed)
    print("feed.json, feed.md et summary.txt générés.")


if __name__ == "__main__":
    main()
