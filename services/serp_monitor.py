"""Serper.dev regional rank snapshots."""

from __future__ import annotations

from urllib.parse import urlparse

import requests

from config import SERPER_API_KEY, SERP_QUERIES, SERPER_URL, SOURCE_SERPER, scrub
from data.db import connect, insert_domain, latest_rank

_SKIP_SUFFIXES = (
    "google.com",
    "google.bg",
    "google.gr",
    "google.ro",
    "google.rs",
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "wikipedia.org",
    "linkedin.com",
)


def _domain(link: str) -> str:
    host = (urlparse(link).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _skipped(domain: str) -> bool:
    return any(domain == suffix or domain.endswith("." + suffix) for suffix in _SKIP_SUFFIXES)


def _message_from(response: requests.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    message = ""
    if isinstance(body, dict):
        raw = body.get("message") or body.get("error")
        if isinstance(raw, dict):
            raw = raw.get("message")
        if isinstance(raw, str):
            message = raw
    if not message and response.status_code in {401, 403}:
        message = "The Serper key was declined."
    elif not message and response.status_code == 429:
        message = "The Serper quota is exhausted."
    elif not message:
        message = f"Serper failed ({response.status_code})."
    return scrub(message)[:180]


def _post(payload: dict) -> dict:
    if not SERPER_API_KEY:
        return {"ok": False, "results": [], "error": "Serper key is not configured."}
    try:
        response = requests.post(
            SERPER_URL,
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json=payload,
            timeout=25,
        )
    except requests.RequestException:
        return {"ok": False, "results": [], "error": "Serper did not respond."}
    if response.status_code >= 400:
        return {"ok": False, "results": [], "error": _message_from(response)}
    try:
        body = response.json()
    except ValueError:
        return {"ok": False, "results": [], "error": "Serper returned an unreadable response."}
    results = []
    for index, item in enumerate(body.get("organic") or [], start=1):
        if not isinstance(item, dict):
            continue
        domain = _domain(str(item.get("link") or ""))
        if not domain or _skipped(domain):
            continue
        try:
            position = int(item.get("position") or index)
        except (TypeError, ValueError):
            position = index
        results.append({"position": position, "domain": domain, "title": str(item.get("title") or domain)})
        if len(results) >= 5:
            break
    return {"ok": True, "results": results, "error": ""}


def fetch_search(query: str, gl: str, hl: str, location: str | None = None) -> dict:
    payload = {"q": query, "gl": gl, "hl": hl, "num": 10}
    if location:
        payload["location"] = location
    result = _post(payload)
    if location and not result["ok"] and "location" in result["error"].lower():
        payload.pop("location", None)
        return _post(payload)
    return result


def _insight(position: int) -> str:
    if position <= 3:
        return (
            f"Position {position} already owns the click. "
            "Attack the page — the offer, the type, the proof — rather than the media budget."
        )
    if position <= 10:
        return f"Position {position} is still on the first screen. Show a calmer page than whoever sits above it."
    return (
        f"Position {position} is off the first screen. "
        "Search can support the story later; the brand system has to carry the first meeting."
    )


def refresh_region(region: str) -> dict:
    queries = SERP_QUERIES.get(region) or []
    if not SERPER_API_KEY:
        return {"ok": False, "stored": 0, "message": "Serper key is not configured. Cached positions stay on screen."}
    if not queries:
        return {"ok": False, "stored": 0, "message": "No search queries are configured for this region."}
    pending = []
    seen = set()
    failed = 0
    for spec in queries:
        result = fetch_search(spec["q"], spec["gl"], spec["hl"], spec.get("location"))
        if not result["ok"]:
            failed += 1
            continue
        for item in result["results"]:
            key = (item["domain"], spec["q"])
            if key in seen:
                continue
            seen.add(key)
            previous = latest_rank(region, item["domain"], spec["q"])
            change = None if previous is None else previous - item["position"]
            pending.append(
                {
                    "region": region,
                    "domain_name": item["domain"],
                    "target_keyword": spec["q"],
                    "rank_position": item["position"],
                    "rank_change": change,
                    "insight": _insight(item["position"]),
                    "source": SOURCE_SERPER,
                }
            )
    if pending:
        with connect() as conn:
            for item in pending:
                insert_domain(item, conn)
    stored = len(pending)
    if stored and not failed:
        message = f"Serper stored {stored} positions across {len(queries)} queries."
        ok = True
    elif stored:
        message = f"Serper stored {stored} positions. {failed} queries did not return."
        ok = True
    elif failed:
        message = "Serper did not return positions. The cached ranks stay on screen."
        ok = False
    else:
        message = "Serper returned no business results. The cached ranks stay on screen."
        ok = False
    return {"ok": ok, "stored": stored, "message": message}
