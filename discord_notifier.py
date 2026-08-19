import json
import os
import re

import requests

COLOR = 0xFFD21E


def clean(value, limit=420):
    text = re.sub(r"\s+", " ", value or "").strip()
    return text if len(text) <= limit else text[:limit - 3] + "..."


def main():
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        raise SystemExit("DISCORD_WEBHOOK_URL is required")
    with open("feed.json", encoding="utf-8") as f:
        feed = json.load(f)
    by_id = {m["id"]: m for m in feed.get("models", [])}
    events = feed.get("current_run_events", [])[:40]
    content = f"**Hugging Face Radar · {len(events)} nouveau(x) signal(aux)**\n{len(by_id)} models/weights surveillés · delta strict du run"
    if not events:
        r = requests.post(webhook, json={"content": content + "\nAucun nouveau signal."}, headers={"User-Agent":"radar-huggingface/1.0"}, timeout=30)
        r.raise_for_status(); return
    embeds=[]
    for event in events:
        m=by_id.get(event["id"],{})
        desc=clean(m.get("card_excerpt") or "Model card non disponible.")
        embeds.append({
            "title": event["id"], "url": m.get("url"), "description": desc, "color": COLOR,
            "fields": [
                {"name":"Signal","value":event["type"],"inline":True},
                {"name":"Type","value":m.get("kind") or "unknown","inline":True},
                {"name":"Downloads","value":str(m.get("downloads") or 0),"inline":True},
            ]
        })
    for i in range(0,len(embeds),10):
        payload={"embeds":embeds[i:i+10]}
        if i==0:payload["content"]=content
        r=requests.post(webhook,json=payload,headers={"User-Agent":"radar-huggingface/1.0"},timeout=30);r.raise_for_status()

if __name__=="__main__":main()
