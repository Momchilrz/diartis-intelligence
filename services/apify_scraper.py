"""Apify client for public TikTok search clips and their opening lines."""

from __future__ import annotations

import re

import requests

from config import APIFY_ACTOR_URL, APIFY_API_TOKEN, APIFY_QUERIES, SOURCE_APIFY, scrub
from data.db import connect, insert_hook

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_HASHTAG = re.compile(r"#\S+")
_EMOJI = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "\uFE0F"
    "\u200D"
    "]+",
    flags=re.UNICODE,
)
_NOT_STATED = re.compile(r"^not stated\b", re.IGNORECASE)


def spoken_line(text: str, *, limit: int = 28) -> str:
    """A sentence a person could say. Hashtags, emoji, and filler are dropped."""
    raw = _EMOJI.sub(" ", text or "")
    raw = _HASHTAG.sub(" ", raw)
    raw = raw.replace("…", " ").replace("...", " ")
    raw = re.sub(r"\s+", " ", raw).strip(" \"'“”")
    if not raw or _NOT_STATED.match(raw):
        return ""
    sentence = _SENTENCE.split(raw)[0].strip()
    words = [word for word in sentence.split() if word]
    if words and len(words[-1]) == 1 and words[-1].isalpha():
        words = words[:-1]
    if len(words) < 3:
        return ""
    words = words[:limit]
    return " ".join(words).strip(" \"'")


def line_insight(line: str) -> str:
    lowered = line.lower()
    if "?" in line or lowered.startswith(("did ", "do you", "why ", "what ", "how ", "am i", "is this")):
        return "Opens on a question. The next frame has to answer it with the client's own case."
    if any(token in lowered for token in ("mistake", "don't", "dont", "stop ", "wrong", "cheap")):
        return "Names a doubt in the first line. Keep the doubt, then show the result."
    if "not" in lowered and "done" in lowered:
        return "The promise is a result that does not look treated. Show one real case and stop talking."
    return "Say this sentence, then show the work. The rest of a caption is explanation, not the opening."


def _opening_line(text: str) -> str:
    return spoken_line(text)


def _blocks(text: str) -> dict:
    raw = _EMOJI.sub(" ", text or "")
    raw = _HASHTAG.sub(" ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    parts = [spoken_line(part, limit=40) for part in _SENTENCE.split(raw) if spoken_line(part, limit=40)]
    labels = ("hook", "friction", "value", "cta")
    return {label: parts[index] if index < len(parts) else "" for index, label in enumerate(labels)}


def archetype_for(text: str) -> str:
    lowered = (text or "").strip().lower()
    if any(token in lowered for token in ("behind the scenes", "in the studio", "we shot", "we filmed", "the process")):
        return "Behind-The-Scenes"
    if lowered.startswith(("stop", "don't", "dont", "do not", "wait", "watch", "pov")):
        return "Pattern Interrupt"
    if any(token in lowered for token in ("mistake", "wrong", "cheap", "template", "nobody", "hate", "ugly", "enough")):
        return "Negative Friction"
    return "Direct Statement"


def present_hook(row: dict) -> dict | None:
    """A card Diana can read. Captions that are only hashtags are dropped."""
    script = row.get("script_structure") if isinstance(row.get("script_structure"), dict) else {}
    line = spoken_line(str(row.get("hook_text") or "")) or spoken_line(str(script.get("hook") or ""))
    if not line:
        for key in ("friction", "value", "cta"):
            line = spoken_line(str(script.get(key) or ""))
            if line:
                break
    if not line:
        return None
    beats = []
    for number, label, key in (
        ("01", "Hook", "hook"),
        ("02", "Customer Friction", "friction"),
        ("03", "Core Value", "value"),
        ("04", "Call to Action", "cta"),
    ):
        text = line if key == "hook" else spoken_line(str(script.get(key) or ""), limit=36)
        if not text or (key != "hook" and text.lower() == line.lower()):
            continue
        beats.append({"number": number, "label": label, "text": text})
    source = str(row.get("source") or "")
    if source == "STUDIO BASELINE" and row.get("insight"):
        insight = str(row["insight"])
        archetype = str(row.get("archetype") or archetype_for(line))
    else:
        insight = line_insight(line)
        archetype = archetype_for(line)
    tier = str(row.get("engagement_tier") or "")
    if tier == "Unranked":
        tier = ""
    return {
        "line": line,
        "beats": beats if len(beats) > 1 else [],
        "insight": insight,
        "archetype": archetype,
        "tier": tier,
        "source": source,
    }


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
                "insight": line_insight(hook),
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
