import json
import math
import os
import re
from collections import OrderedDict

import requests

COLOR = 0xFFD21E
MAX_EVENTS = 60
MAX_EMBEDS_PER_MESSAGE = 8
MAX_LINES_PER_EMBED = 12


def clean(value, limit=120):
    text = re.sub(r"\s+", " ", value or "").strip()
    text = re.sub(r"[#*_`>|]", "", text)
    return text if len(text) <= limit else text[:limit - 3] + "..."


def family(model):
    text = " ".join([
        model.get("id") or "",
        " ".join(model.get("tags") or []),
        model.get("card_excerpt") or "",
    ]).lower()
    if any(k in text for k in ["minimax", "h3"]):
        return "🎬 MiniMax H3", "h3"
    if any(k in text for k in ["ltx", "lightricks"]):
        return "🎥 LTX", "ltx"
    if "wan" in text:
        return "🌊 Wan", "wan"
    if any(k in text for k in ["qwen-image", "qwen image"]):
        return "🖼️ Qwen Image", "qwen"
    if "flux" in text:
        return "✨ Flux", "flux"
    return "📦 Autres models / weights", "other"


def kind_label(model):
    kind = (model.get("kind") or "unknown").lower()
    labels = {
        "lora": "LoRA",
        "adapter": "Adapter",
        "quantization": "Quant",
        "base": "Base",
        "utility": "Utility",
        "unknown": "Weight",
    }
    return labels.get(kind, kind.title())


def short_description(model):
    card = clean(model.get("card_excerpt") or "", 105)
    if card:
        return card
    tags = [t for t in (model.get("tags") or []) if not t.startswith("license:")][:4]
    return clean(" · ".join(tags) or "Model card non disponible", 105)


def line_for(event, model):
    model_id = event.get("id") or model.get("id") or "model"
    name = model_id.split("/")[-1]
    url = model.get("url") or f"https://huggingface.co/{model_id}"
    desc = short_description(model)
    downloads = model.get("downloads") or 0
    likes = model.get("likes") or 0
    meta = [event.get("type") or "EVENT", kind_label(model)]
    if downloads:
        meta.append(f"↓{downloads}")
    if likes:
        meta.append(f"♥{likes}")
    return f"• **[{clean(name, 62)}]({url})** — {desc}  `{' · '.join(meta)}`"


def build_embeds(events, by_id):
    groups = OrderedDict([
        ("h3", ("🎬 MiniMax H3", [])),
        ("ltx", ("🎥 LTX", [])),
        ("wan", ("🌊 Wan", [])),
        ("qwen", ("🖼️ Qwen Image", [])),
        ("flux", ("✨ Flux", [])),
        ("other", ("📦 Autres models / weights", [])),
    ])
    for event in events:
        model = by_id.get(event.get("id"), {})
        _, key = family(model)
        groups[key][1].append(line_for(event, model))

    embeds = []
    for _, (title, lines) in groups.items():
        if not lines:
            continue
        for start in range(0, len(lines), MAX_LINES_PER_EMBED):
            suffix = "" if start == 0 else " · suite"
            embeds.append({
                "title": title + suffix,
                "description": "\n".join(lines[start:start + MAX_LINES_PER_EMBED])[:3900],
                "color": COLOR,
            })
    return embeds


def main():
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        raise SystemExit("DISCORD_WEBHOOK_URL is required")

    with open("feed.json", encoding="utf-8") as f:
        feed = json.load(f)

    by_id = {m["id"]: m for m in feed.get("models", [])}
    events = feed.get("current_run_events", [])[:MAX_EVENTS]

    if not events:
        payload = {"content": f"**🟡 HF Radar · aucun nouveau signal**\n{len(by_id)} models/weights surveillés"}
        response = requests.post(webhook, json=payload, headers={"User-Agent": "radar-huggingface/1.1"}, timeout=30)
        response.raise_for_status()
        return

    embeds = build_embeds(events, by_id)
    pages = max(1, math.ceil(len(embeds) / MAX_EMBEDS_PER_MESSAGE))
    new_count = sum(1 for e in events if e.get("type") == "NEW")
    update_count = len(events) - new_count

    for page in range(pages):
        batch = embeds[page * MAX_EMBEDS_PER_MESSAGE:(page + 1) * MAX_EMBEDS_PER_MESSAGE]
        content = (
            f"**🟡 HF Radar · {len(events)} signaux · {new_count} NEW · {update_count} UPDATE**"
            f"  ·  page {page + 1}/{pages}\n"
            f"{len(by_id)} models/weights surveillés · delta strict du run"
        )
        response = requests.post(
            webhook,
            json={"content": content, "embeds": batch},
            headers={"User-Agent": "radar-huggingface/1.1"},
            timeout=30,
        )
        response.raise_for_status()


if __name__ == "__main__":
    main()
