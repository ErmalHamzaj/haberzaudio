#!/usr/bin/env python3
"""
HaberZ Bülten Audio Generator
Fetches top 10 Sabah Gündem headlines and generates a TTS bulletin via OpenAI.
Output: audio-output/bulten_morning.mp3  (run before 17:00 Istanbul)
         audio-output/bulten_evening.mp3  (run at/after 17:00 Istanbul)
"""

import datetime
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
RSS_URL = "https://www.sabah.com.tr/rss/gundem.xml"
OUTPUT_DIR = "audio-output"

# Phrases that appear in RSS feeds but should never be spoken aloud
_JUNK = re.compile(
    r"(Son Dakika[!:]?|SON DAKİKA[!:]?|Devamın?ı? için tıklayınız\.?|"
    r"Haberin devamı(nı)? için tıklayınız\.?|Devamını oku\.?|"
    r"Haber için tıklayınız\.?|>> ?Tıklayınız\.?|tıklayınız\.?|"
    r"https?://\S+|\[.*?\]|\(.*?\))",
    re.IGNORECASE,
)
_HTML = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s{2,}")


def clean(text: str) -> str:
    text = _HTML.sub(" ", text)
    text = _JUNK.sub(" ", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip(" .")


def fetch_headlines(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "HaberZ-Bot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    root = ET.fromstring(data)
    items = []
    for item in root.iter("item"):
        title = clean(item.findtext("title", ""))
        desc = clean(item.findtext("description", ""))
        if title:
            items.append({"title": title, "description": desc})
        if len(items) >= 10:
            break
    return items


def build_script(items: list[dict], label: str) -> str:
    parts = [
        f"HaberZ {label} Haber Bülteni.",
        "İşte günün öne çıkan haberleri.",
    ]
    for item in items:
        segment = item["title"] + "."
        desc = item["description"]
        if len(desc) > 20:
            # First two sentences only — keep it concise
            sentences = [s.strip() for s in desc.split(". ") if s.strip()]
            snippet = ". ".join(sentences[:2])
            if snippet and not snippet.endswith("."):
                snippet += "."
            segment += " " + snippet
        parts.append(segment)
    parts.append("HaberZ günlük bültenini dinlediğiniz için teşekkürler.")
    return " ".join(parts)


def call_tts(text: str) -> bytes:
    payload = json.dumps(
        {"model": "tts-1-hd", "input": text, "voice": "onyx",
         "response_format": "mp3", "speed": 1.0}
    ).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/speech",
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main() -> None:
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    istanbul = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(istanbul)

    if now.hour >= 17:
        label, filename = "Akşam", "bulten_evening.mp3"
    else:
        label, filename = "Sabah", "bulten_morning.mp3"

    print(f"[{now.strftime('%H:%M')} Istanbul] Generating {label} bulletin → {filename}")

    headlines = fetch_headlines(RSS_URL)
    if not headlines:
        print("ERROR: No headlines fetched from RSS.", file=sys.stderr)
        sys.exit(1)
    print(f"Fetched {len(headlines)} headlines.")

    script = build_script(headlines, label)
    print(f"Script preview: {script[:180]}…")

    audio = call_tts(script)
    print(f"Audio size: {len(audio):,} bytes")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = os.path.join(OUTPUT_DIR, filename)
    with open(out, "wb") as f:
        f.write(audio)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
