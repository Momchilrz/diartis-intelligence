"""Public page read: how a site is built, how it measures, and what to raise."""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import SOURCE_HEADERS
from services.color_extractor import extract_from_url, safe_hex
from services.net import UrlError, fetch_public

_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_FONT = re.compile(r"family=([^:&\"']+)")
_PHONE = re.compile(r"(?:\+359|0)[\d\s().-]{6,}\d")

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
    ("TikTok Pixel", ["analytics.tiktok.com", "ttq.load"]),
    ("Google Ads", ["googleadservices.com", "gtag('config', 'aw-"]),
    ("LinkedIn Insight", ["snap.licdn.com", "linkedin.com/insight"]),
    ("HubSpot", ["js.hs-scripts.com", "hs-scripts.com"]),
    ("Cookie banner", ["cookiebot", "cookieyes", "onetrust"]),
    ("WhatsApp", ["wa.me", "api.whatsapp.com"]),
]

_MEASUREMENT = {
    "Google Tag Manager",
    "Meta Pixel",
    "Google Analytics 4",
    "Hotjar",
    "TikTok Pixel",
    "Google Ads",
    "LinkedIn Insight",
    "HubSpot",
}
_CMS = {"WordPress", "Shopify", "WooCommerce", "Webflow"}


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
    return {"tags": tags, "notes": notes, "generator": generator}


def _text(value) -> str:
    return " ".join(str(value or "").split())


def _meta(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": lambda found: isinstance(found, str) and found.lower() == name})
    if tag and tag.get("content"):
        return _text(tag["content"])
    tag = soup.find("meta", attrs={"property": lambda found: isinstance(found, str) and found.lower() == name})
    if tag and tag.get("content"):
        return _text(tag["content"])
    return ""


def _colors_from_html(soup: BeautifulSoup) -> list[str]:
    blobs = []
    for tag in soup.find_all(style=True):
        blobs.append(str(tag.get("style")))
    for tag in soup.find_all("style"):
        if tag.string:
            blobs.append(str(tag.string))
    counts: Counter[str] = Counter()
    for blob in blobs:
        for match in _HEX.findall(blob):
            hex_code = match.upper()
            if len(hex_code) == 3:
                hex_code = "".join(channel * 2 for channel in hex_code)
            if hex_code in {"FFFFFF", "000000", "FFF", "000"}:
                continue
            counts[f"#{hex_code}"] += 1
    return [safe_hex(color) for color, _ in counts.most_common(5)]


def _fonts(soup: BeautifulSoup) -> list[str]:
    found = []
    for tag in soup.find_all("link", href=True):
        href = str(tag["href"])
        if "fonts.googleapis.com" not in href and "fonts.gstatic.com" not in href:
            continue
        for family in _FONT.findall(href):
            name = family.replace("+", " ").split("|")[0].strip()
            if name and name not in found:
                found.append(name)
    return found[:4]


def _contacts(soup: BeautifulSoup) -> dict:
    phones = []
    emails = []
    whatsapp = False
    for tag in soup.find_all("a", href=True):
        href = str(tag["href"])
        lowered = href.lower()
        if lowered.startswith("tel:"):
            phones.append(_text(href[4:]))
        elif lowered.startswith("mailto:"):
            emails.append(_text(href[7:].split("?")[0]))
        elif "wa.me" in lowered or "api.whatsapp.com" in lowered:
            whatsapp = True
    if not phones:
        for match in _PHONE.findall(soup.get_text(" ", strip=True)[:8000]):
            phones.append(_text(match))
            if len(phones) >= 3:
                break
    return {
        "phones": list(dict.fromkeys(phones))[:3],
        "emails": list(dict.fromkeys(emails))[:3],
        "whatsapp": whatsapp,
    }


def _ctas(soup: BeautifulSoup) -> list[str]:
    labels = []
    for tag in soup.find_all(["a", "button"]):
        label = _text(tag.get_text(" ", strip=True))
        if not label or len(label) > 42 or label in labels:
            continue
        href = str(tag.get("href") or "")
        classes = " ".join(tag.get("class") or []).lower()
        if tag.name == "button" or "btn" in classes or "button" in classes or href.startswith(("tel:", "mailto:")) or "wa.me" in href:
            labels.append(label)
        if len(labels) >= 6:
            break
    return labels


def _findings(page: dict) -> list[dict]:
    findings = []

    def add(kind: str, title: str, detail: str) -> None:
        findings.append({"kind": kind, "title": title, "detail": detail})

    if page["https"]:
        add("ok", "The address is secure", "The page opens on https, so a visitor is not warned before they arrive.")
    else:
        add("raise", "The address is not secure", "The page is still on http. That is the first thing a careful client notices.")

    title = page["title"]
    if title and len(title) > 8:
        add("ok", "The tab says what this is", title)
    else:
        add("raise", "The tab title does not explain the business", "Search and browser tabs are showing a weak or empty name.")

    h1s = page["h1s"]
    if len(h1s) == 1:
        add("ok", "There is one headline", h1s[0])
    elif not h1s:
        add("raise", "There is no headline", "A visitor has to guess what the page is for.")
    else:
        add("raise", "Several headlines compete", " · ".join(h1s[:3]))

    if len(page["description"]) > 40:
        add("ok", "Search has a sentence to quote", page["description"][:180])
    else:
        add("raise", "Search has little to quote", "The page is missing a proper description, so Google writes one.")

    if page["phones"] or page["emails"] or page["whatsapp"]:
        contact = ", ".join(page["phones"] + page["emails"])
        if page["whatsapp"]:
            contact = (contact + ", WhatsApp").strip(", ")
        add("ok", "A next step is on the page", contact or "WhatsApp")
    else:
        add("raise", "No phone, email, or WhatsApp in the public page", "The pitch can offer one obvious way to start.")

    measured = [tag for tag in page["tags"] if tag in _MEASUREMENT]
    if measured:
        add("ok", "The page is measuring something", ", ".join(measured))
    else:
        add(
            "raise",
            "No public measurement",
            "Analytics, ads, and the Meta pixel are not in the HTML this desk can see. A campaign on this site is hard to prove.",
        )

    if page["og_image"]:
        add("ok", "The link has a picture", "Pasting the address into a chat shows an image.")
    else:
        add("raise", "The link has no picture", "Shared in a message, this address is only a title.")

    if "Cookie banner" in page["tags"]:
        add("ok", "A consent tool is present", "They have started to treat tracking as something a visitor can refuse.")

    return findings


def _summary(page: dict, findings: list[dict]) -> str:
    built = [tag for tag in page["tags"] if tag in _CMS]
    platform = built[0] if built else "a custom page"
    raises = [item["title"].lower() for item in findings if item["kind"] == "raise"]
    if not raises:
        return f"This is {platform}. The public page already says what it is, how to start, and how a visit is counted."
    return f"This is {platform}. In the meeting, raise {raises[0]}."


def inspect_url(url: str) -> dict:
    empty = {
        "ok": False,
        "tags": [],
        "notes": [],
        "final_url": "",
        "error": "",
        "source": SOURCE_HEADERS,
        "page": {},
        "findings": [],
        "summary": "",
        "colors": [],
        "image_colors": [],
    }
    try:
        fetched = fetch_public(url, timeout=12, max_bytes=1_500_000)
    except UrlError as exc:
        empty["error"] = str(exc)
        return empty
    except requests.RequestException:
        empty["error"] = "The site did not respond."
        return empty
    if fetched["status"] >= 400:
        empty["final_url"] = fetched["url"]
        empty["error"] = f"The page returned {fetched['status']}."
        return empty
    content_type = fetched["headers"].get("Content-Type", fetched["headers"].get("content-type", ""))
    if content_type and "html" not in content_type.lower() and "xml" not in content_type.lower() and "text/" not in content_type.lower():
        empty["final_url"] = fetched["url"]
        empty["error"] = "That address did not return a web page."
        return empty
    html = fetched["content"].decode("utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    found = detect_from_html(html, fetched["headers"])
    h1s = [_text(tag.get_text(" ", strip=True)) for tag in soup.find_all("h1")]
    h1s = [line for line in h1s if line][:4]
    contacts = _contacts(soup)
    og_image = _meta(soup, "og:image")
    if og_image:
        og_image = urljoin(fetched["url"], og_image)
    page = {
        "title": _text(soup.title.string if soup.title else "") or _meta(soup, "og:title"),
        "description": _meta(soup, "description") or _meta(soup, "og:description"),
        "h1s": h1s,
        "lang": (soup.html.get("lang") if soup.html else "") or "",
        "https": urlparse(fetched["url"]).scheme == "https",
        "phones": contacts["phones"],
        "emails": contacts["emails"],
        "whatsapp": contacts["whatsapp"],
        "ctas": _ctas(soup),
        "fonts": _fonts(soup),
        "forms": len(soup.find_all("form")),
        "og_image": og_image,
        "generator": found.get("generator") or "",
        "tags": found["tags"],
    }
    findings = _findings(page)
    colors = _colors_from_html(soup)
    image_colors = []
    if og_image:
        image = extract_from_url(og_image)
        if image.get("ok"):
            image_colors = image.get("colors") or []
    notes = []
    if page["generator"]:
        notes.append(f"Generator: {page['generator'][:90]}")
    if page["fonts"]:
        notes.append("Fonts: " + ", ".join(page["fonts"]))
    if page["forms"]:
        notes.append(f"{page['forms']} form{'s' if page['forms'] != 1 else ''} on the page")
    return {
        "ok": True,
        "tags": found["tags"],
        "notes": notes,
        "final_url": fetched["url"],
        "error": "",
        "source": SOURCE_HEADERS,
        "page": page,
        "findings": findings,
        "summary": _summary(page, findings),
        "colors": colors,
        "image_colors": image_colors,
    }
