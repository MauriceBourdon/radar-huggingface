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


def model_text(model):
    return " ".join([
        model.get("id") or "",
        " ".join(model.get("tags") or []),
        model.get("card_excerpt") or "",
        model.get("pipeline_tag") or "",
        model.get("library_name") or "",
    ]).lower()


def has_any(text, keywords):
    return any(k in text for k in keywords)


def category(model):
    text = model_text(model)
    pipeline = (model.get("pipeline_tag") or "").lower()

    if has_any(text, [
        "text-to-video", "image-to-video", "video-to-video", "video-generation",
        "video generation", "t2v", "i2v", "ltx", "wan2", "wan 2", "hunyuanvideo",
        "hunyuan video", "mochi", "cogvideo", "animatediff", "minimax h3", "minimax-h3",
    ]) or "video" in pipeline:
        return "🎥 Vidéo / Motion", "video"

    if has_any(text, [
        "text-to-image", "image-to-image", "image-to-image", "image-generation",
        "image generation", "inpaint", "outpaint", "upscale", "super-resolution",
        "controlnet", "ip-adapter", "ipadapter", "flux", "qwen-image", "qwen image",
        "stable diffusion", "sdxl", "sd3", "kolors", "lumina image",
    ]) or "image" in pipeline:
        return "🖼️ Image", "image"

    if has_any(text, [
        "text-to-audio", "audio-to-audio", "text-to-speech", "automatic-speech-recognition",
        "audio generation", "music", "tts", "speech", "voice", "suno", "ace-step",
        "stable audio", "audio",
    ]) or "audio" in pipeline or "speech" in pipeline:
        return "🔊 Audio / Music", "audio"

    if has_any(text, [
        "text-to-3d", "image-to-3d", "3d", "mesh", "gaussian splat", "point cloud",
        "texture generation", "texturing", "trellis", "hunyuan3d", "tripo",
    ]) or "3d" in pipeline:
        return "🧊 3D", "3d"

    if has_any(text, [
        "vision-language", "visual question answering", "image-text-to-text", "multimodal",
        "vlm", "qwen-vl", "qwen3-vl", "llava", "internvl", "florence",
    ]):
        return "👁️ Vision / Multimodal", "vision"

    if has_any(text, [
        "text-generation", "text2text-generation", "sentence-transformers", "embedding",
        "llm", "language model", "text encoder", "clip text", "t5", "umt5", "gemma",
    ]) or "text" in pipeline:
        return "🧠 Text / Encoders", "text"

    kind = (model.get("kind") or "").lower()
    if kind in {"quantization", "adapter", "utility"} or has_any(text, [
        "quant", "gguf", "awq", "gptq", "fp8", "int8", "nf4", "bnb", "adapter",
        "vae", "clip", "encoder", "utility", "conversion", "comfyui",
    ]):
        return "🛠️ Components / Utilities", "components"

    return "📦 Other models / weights", "other"


def ecosystem_tags(model):
    text = model_text(model)
    candidates = [
        ("H3", ["minimax h3", "minimax-h3", "minimax_h3", " h3 ", "h3-"]),
        ("MiniMax", ["minimax"]),
        ("LTX", ["ltx-", "ltx ", "lightricks"]),
        ("Wan", ["wan2", "wan 2", "wan-video", "wan video", "wan2.1", "wan2.2", "wan2.6"]),
        ("Flux", ["flux", "black-forest-labs", "black forest labs"]),
        ("Qwen", ["qwen"]),
        ("Suno", ["suno"]),
        ("ACE-Step", ["ace-step", "ace step"]),
        ("SDXL", ["sdxl"]),
        ("SD3", ["stable diffusion 3", "sd3"]),
        ("ControlNet", ["controlnet"]),
        ("LoRA", ["lora"]),
        ("GGUF", ["gguf"]),
        ("FP8", ["fp8", "float8"]),
    ]
    tags = []
    for label, keywords in candidates:
        if has_any(text, keywords) and label not in tags:
            tags.append(label)
    if "H3" in tags and "MiniMax" in tags:
        tags.remove("MiniMax")
    return tags[:4]


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
    meta.extend(ecosystem_tags(model))
    if downloads:
        meta.append(f"↓{downloads}")
    if likes:
        meta.append(f"♥{likes}")
    return f"• **[{clean(name, 62)}]({url})** — {desc}  `{' · '.join(meta)}`"


def build_embeds(events, by_id):
    groups = OrderedDict([
        ("image", ("🖼️ Image", [])),
        ("video", ("🎥 Vidéo / Motion", [])),
        ("audio", ("🔊 Audio / Music", [])),
        ("3d", ("🧊 3D", [])),
        ("vision", ("👁️ Vision / Multimodal", [])),
        ("text", ("🧠 Text / Encoders", [])),
        ("components", ("🛠️ Components / Utilities", [])),
        ("other", ("📦 Other models / weights", [])),
    ])
    for event in events:
        model = by_id.get(event.get("id"), {})
        _, key = category(model)
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
        response = requests.post(webhook, json=payload, headers={"User-Agent": "radar-huggingface/1.2"}, timeout=30)
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
            headers={"User-Agent": "radar-huggingface/1.2"},
            timeout=30,
        )
        response.raise_for_status()


if __name__ == "__main__":
    main()
