"""Environment loading and the constants the desk shares."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
load_dotenv(ROOT / ".env")


def _env(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        try:
            import streamlit as st

            if name in st.secrets:
                value = str(st.secrets[name])
        except Exception:
            value = ""
    return value.strip().strip('"').strip("'")


SERPER_API_KEY = _env("SERPER_API_KEY")
APIFY_API_TOKEN = _env("APIFY_API_TOKEN")
DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY")
STUDIO_PASSCODE = _env("STUDIO_PASSCODE")


def scrub(text: str) -> str:
    cleaned = text or ""
    for secret in (SERPER_API_KEY, APIFY_API_TOKEN, DEEPSEEK_API_KEY, STUDIO_PASSCODE):
        if secret:
            cleaned = cleaned.replace(secret, "…")
    return cleaned

DB_PATH = Path(os.getenv("DIARTIS_DB_PATH", DATA_DIR / "intel_store.db"))

SERPER_URL = "https://google.serper.dev/search"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
# deepseek-chat was retired in July 2026. Pro writes the pitch; flash is the fallback.
DEEPSEEK_MODELS = ["deepseek-v4-pro", "deepseek-flash"]
APIFY_ACTOR_URL = (
    "https://api.apify.com/v2/acts/clockworks~tiktok-scraper/run-sync-get-dataset-items"
)

USER_AGENT = "diArtisStudioIntel/1.0 (+https://diartis.studio)"

SOURCE_BASELINE = "STUDIO BASELINE"
SOURCE_SERPER = "SERPER API"
SOURCE_APIFY = "APIFY TIKTOK"
SOURCE_DEEPSEEK = "DEEPSEEK"
SOURCE_HEADERS = "PUBLIC PAGE HEADERS"
SOURCE_COLOR = "LOCAL COLOR CLUSTER"
SOURCE_BRAND = "DIARTIS BRAND TONES"

BRAND_PALETTE = ["#4C5539", "#8C947D", "#F8F8F5", "#1A1A1A", "#E2E2DC"]

REGIONS = [
    {"id": "varna_razgrad", "label": "📍 Varna / Razgrad", "short": "Varna / Razgrad"},
    {"id": "bulgaria", "label": "🇧🇬 Bulgaria", "short": "Bulgaria"},
    {"id": "greece_romania", "label": "🇬🇷 🇷🇴 Greece & Romania", "short": "Greece & Romania"},
    {"id": "balkans", "label": "🌍 Balkans", "short": "Balkans"},
    {"id": "world", "label": "🌐 World", "short": "World"},
]

TIMEFRAMES = {
    "24 Hours": "-1 day",
    "7 Days": "-7 days",
    "30 Days": "-30 days",
}

REGION_IDS = {item["id"] for item in REGIONS}
LABEL_TO_REGION = {item["label"]: item for item in REGIONS}

# One refresh reads these queries only. Counts stay small on purpose.
SERP_QUERIES = {
    "varna_razgrad": [
        {"q": "дигитален маркетинг варна", "gl": "bg", "hl": "bg", "location": "Varna, Bulgaria"},
        {"q": "зъбни импланти разград", "gl": "bg", "hl": "bg", "location": "Razgrad, Bulgaria"},
        {"q": "интериорен дизайн варна", "gl": "bg", "hl": "bg", "location": "Varna, Bulgaria"},
    ],
    "bulgaria": [
        {"q": "creative agency sofia", "gl": "bg", "hl": "en", "location": "Sofia, Bulgaria"},
        {"q": "брандинг агенция софия", "gl": "bg", "hl": "bg", "location": "Sofia, Bulgaria"},
    ],
    "greece_romania": [
        {"q": "digital agency thessaloniki", "gl": "gr", "hl": "en", "location": "Thessaloniki, Greece"},
        {"q": "agentie branding bucuresti", "gl": "ro", "hl": "ro", "location": "Bucharest, Romania"},
    ],
    "balkans": [
        {"q": "branding agency belgrade", "gl": "rs", "hl": "en", "location": "Belgrade, Serbia"},
        {"q": "design studio athens", "gl": "gr", "hl": "en", "location": "Athens, Greece"},
    ],
    "world": [
        {"q": "boutique branding studio", "gl": "us", "hl": "en", "location": None},
        {"q": "editorial website design", "gl": "us", "hl": "en", "location": None},
    ],
}

APIFY_QUERIES = {
    "varna_razgrad": "porcelain veneers",
    "bulgaria": "branding studio sofia",
    "greece_romania": "aesthetic clinic bucharest",
    "balkans": "boutique hotel design",
    "world": "brand identity process",
}
