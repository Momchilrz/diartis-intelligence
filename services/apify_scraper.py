"""Apify client for public TikTok search clips and their opening lines."""

from __future__ import annotations

import re

import requests

from config import APIFY_ACTOR_URL, APIFY_API_TOKEN, APIFY_QUERIES, SOURCE_APIFY, scrub
from data.db import connect, insert_hook

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _opening_line(text: str) -> str:
    clean = " ".join((text or "").split())
    if not clean:
        return ""
    line = _SENTENCE.split(clean)[0].strip()
    if len(line) > 180:
        line = line[:177].rstrip() + "…"
    return line


def _blocks(text: str) -> dict:
    parts = [part.strip() for part in _SENTENCE.split(" ".join((text or "").split())) if part.strip()]
    labels = ("hook", "friction", "value", "cta")
    blocks = {}
    for index, label in enumerate(labels):
        blocks[label] = parts[index] if index < len(parts) else "Not stated in the public caption."
    return blocks


def archetype_for(text: str) -> str:
    lowered = (text or "").strip().lower()
    if any(token in lowered for token in ("behind the scenes", "in the studio", "we shot", "we filmed", "the process")):
        return "Behind-The-Scenes"
    if lowered.startswith(("stop", "don't", "dont", "do not", "wait", "watch", "pov")):
        return "Pattern Interrupt"
    if any(token in lowered for token in ("mistake", "wrong", "cheap", "template", "nobody", "hate", "ugly", "enough")):
        return "Negative Friction"
    return "Direct Statement"


def _tier(play_count) -> str:
    try:
        plays = int(play_count)
    except (TypeError, ValueError):
        return "Unranked"
    if plays >= 1_000_000:
        return "Breakout"
    if plays >= 100_000:
        return "High velocity"
    if plays >= 10_000:
        return "Emerging"
    return "Quiet"


def _speech(item: dict) -> str:
    subtitles = item.get("subtitles") or item.get("subtitleText")
    if isinstance(subtitles, str) and subtitles.strip():
        return subtitles.strip()
    if isinstance(subtitles, list):
        for entry in subtitles:
            if isinstance(entry, dict) and str(entry.get("text") or "").strip():
                return str(entry["text"]).strip()
            if isinstance(entry, str) and entry.strip():
                return entry.strip()
    return str(item.get("text") or "").strip()


def _audio(item: dict) -> str:
    music = item.get("musicMeta") if isinstance(item.get("musicMeta"), dict) else {}
    name = str(music.get("musicName") or "").strip()
    author = str(music.get("musicAuthor") or "").strip()
    if name and author:
        return f"{name} — {author}"
    return name or author or "Audio not listed"


def rows_from_items(items: list, region: str) -> list[dict]:
    rows = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        speech = _speech(item)
        hook = _opening_line(speech)
        if not hook or hook in seen:
            continue
        seen.add(hook)
        archetype = archetype_for(hook)
        tier = _tier(item.get("playCount"))
        blocks = _blocks(speech)
        blocks["hook"] = hook
        blocks["audio"] = _audio(item)
        video = item.get("videoMeta") if isinstance(item.get("videoMeta"), dict) else {}
        if video.get("duration") is not None:
            blocks["duration_seconds"] = video.get("duration")
        rows.append(
            {
                "region": region,
                "hook_text": hook,
                "archetype": archetype,
                "engagement_tier": tier,
                "script_structure": blocks,
                "insight": (
                    f"{archetype} opening on a {tier.lower()} public clip. "
                    "Lift the sentence shape, then replace the proof with the client's own work."
                ),
                "source": SOURCE_APIFY,
            }
        )
    return rows


def _error_text(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    message = ""
    if isinstance(body, dict):
        raw = body.get("error")
        if isinstance(raw, dict):
            message = str(raw.get("message") or "")
        elif isinstance(raw, str):
            message = raw
        message = message or str(body.get("message") or "")
    if not message and response.status_code in {401, 403}:
        message = "The Apify token was declined."
    elif not message and response.status_code == 402:
        message = "The Apify account cannot start this run."
    elif not message:
        message = f"Apify failed ({response.status_code})."
    return scrub(message)[:200]


def fetch_items(query: str) -> dict:
    if not APIFY_API_TOKEN:
        return {"ok": False, "items": [], "error": "Apify token is not configured."}
    payload = {
        "searchQueries": [query],
        "resultsPerPage": 3,
        "searchSection": "/video",
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSlideshowImages": False,
        "shouldDownloadAvatars": False,
        "shouldDownloadMusicCovers": False,
        "shouldDownloadSubtitles": False,
        "scrapeRelatedVideos": False,
    }
    try:
        response = requests.post(
            APIFY_ACTOR_URL,
            params={"timeout": 45},
            headers={"Authorization": f"Bearer {APIFY_API_TOKEN}", "Content-Type": "application/json"},
            json=payload,
            timeout=70,
        )
    except requests.Timeout:
        return {"ok": False, "items": [], "error": "The TikTok index timed out."}
    except requests.RequestException:
        return {"ok": False, "items": [], "error": "The TikTok index did not respond."}
    if response.status_code >= 400:
        return {"ok": False, "items": [], "error": _error_text(response)}
    try:
        body = response.json()
    except ValueError:
        return {"ok": False, "items": [], "error": "The TikTok index returned an unreadable response."}
    if isinstance(body, dict):
        message = _error_text(response) if body.get("error") else "The TikTok index returned no clips."
        return {"ok": False, "items": [], "error": message}
    if not isinstance(body, list):
        return {"ok": False, "items": [], "error": "The TikTok index returned an unexpected payload."}
    return {"ok": True, "items": body, "error": ""}


def refresh_region(region: str) -> dict:
    query = APIFY_QUERIES.get(region)
    if not APIFY_API_TOKEN:
        return {"ok": False, "stored": 0, "message": "Apify token is not configured. Cached hooks stay on screen."}
    if not query:
        return {"ok": False, "stored": 0, "message": "No short-form query is configured for this region."}
    fetched = fetch_items(query)
    if not fetched["ok"]:
        return {
            "ok": False,
            "stored": 0,
            "message": f"{fetched['error']} Cached hooks stay on screen.",
        }
    rows = rows_from_items(fetched["items"], region)
    if not rows:
        return {
            "ok": False,
            "stored": 0,
            "message": "The TikTok index returned no opening lines. Cached hooks stay on screen.",
        }
    with connect() as conn:
        for row in rows:
            insert_hook(row, conn)
    return {
        "ok": True,
        "stored": len(rows),
        "message": f"TikTok index stored {len(rows)} opening lines for “{query}”.",
    }
