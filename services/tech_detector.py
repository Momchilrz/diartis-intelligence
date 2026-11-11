"""Public HTML scan for marketing pixels, CMS platforms, and booking tools."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from config import SOURCE_HEADERS
from services.net import UrlError, fetch_public

SIGNATURES = [
    ("Google Tag Manager", ["googletagmanager.com/gtm.js", "gtm.start", "gtm.js"]),
    ("Meta Pixel", ["connect.facebook.net", "fbevents.js", "fbq("]),
    ("Google Analytics 4", ["gtag/js?id=g-", "id=g-", "gtag('config', 'g-"]),
    ("WordPress", ["wp-content/", "wp-includes/"]),
    ("Shopify", ["cdn.shopify.com", "myshopify.com", "shopify.theme"]),
    ("WooCommerce", ["woocommerce", "wc-ajax"]),
    ("Webflow", ["data-wf-site", "webflow.js", "website-files.com"]),
    ("Calendly", ["calendly.com"]),
    ("Hotjar", ["hotjar.com", "hj("]),
]


def detect_from_html(html: str, headers: dict | None = None) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
    pieces: list[str] = []
    for tag in soup.find_all(["script", "link", "img", "iframe", "meta"]):
        for attr in ("src", "href", "content", "data-src"):
            value = tag.get(attr)
            if value:
                pieces.append(str(value))
        if tag.name == "script" and tag.string:
            pieces.append(str(tag.string))
    if soup.find(attrs={"data-wf-site": True}):
        pieces.append("data-wf-site")
    generator = ""
    meta = soup.find("meta", attrs={"name": lambda name: isinstance(name, str) and name.lower() == "generator"})
    if meta and meta.get("content"):
        generator = str(meta["content"])
        pieces.append(generator)
    for key, value in (headers or {}).items():
        pieces.append(f"{key}:{value}")
    haystack = "\n".join(pieces).lower()
    tags = [name for name, tokens in SIGNATURES if any(token in haystack for token in tokens)]
    notes = []
    if generator:
        notes.append(f"Generator: {generator[:90]}")
    if not tags and len(haystack) < 400:
        notes.append("Little measurable markup in the server HTML. A client-rendered site can hide its pixels from this scan.")
    return {"tags": tags, "notes": notes}


def inspect_url(url: str) -> dict:
    try:
        fetched = fetch_public(url, timeout=12, max_bytes=1_500_000)
    except UrlError as exc:
        return {"ok": False, "tags": [], "notes": [], "final_url": "", "error": str(exc), "source": SOURCE_HEADERS}
    except requests.RequestException:
        return {
            "ok": False,
            "tags": [],
            "notes": [],
            "final_url": "",
            "error": "The site did not respond.",
            "source": SOURCE_HEADERS,
        }
    if fetched["status"] >= 400:
        return {
            "ok": False,
            "tags": [],
            "notes": [],
            "final_url": fetched["url"],
            "error": f"The page returned {fetched['status']}.",
            "source": SOURCE_HEADERS,
        }
    content_type = fetched["headers"].get("Content-Type", fetched["headers"].get("content-type", ""))
    if content_type and "html" not in content_type.lower() and "xml" not in content_type.lower() and "text/" not in content_type.lower():
        return {
            "ok": False,
            "tags": [],
            "notes": [],
            "final_url": fetched["url"],
            "error": "That address did not return HTML.",
            "source": SOURCE_HEADERS,
        }
    try:
        html = fetched["content"].decode("utf-8", errors="ignore")
    except Exception:
        html = ""
    found = detect_from_html(html, fetched["headers"])
    return {
        "ok": True,
        "tags": found["tags"],
        "notes": found["notes"],
        "final_url": fetched["url"],
        "error": "",
        "source": SOURCE_HEADERS,
    }
