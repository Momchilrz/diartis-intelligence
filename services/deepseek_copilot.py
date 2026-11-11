"""DeepSeek pitch strategist for diArtis Studio."""

from __future__ import annotations

import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_MODELS, DEEPSEEK_URL, scrub

SYSTEM_PROMPT = """You are the Senior Creative Strategist at diArtis Studio, a high-end digital studio in Bulgaria.
Write for Diana Ruseva, Creative Director. The reader has severe taste and no patience for agency filler.
Use precise, editorial English. No emoji. No hype. No "elevate", "unlock", "bespoke journey", or "digital landscape".
Use only the regional evidence provided. Studio baseline rows are rehearsal material, not live measurements. Say so in a clause when you rely on them, then still make a decisive recommendation.
Do not invent rankings, budgets, or conversion rates.

Structure the answer in exactly these three headings, each on its own line:

1. VISUAL DIRECTION & COLOR POSITIONING
2. SHORT-FORM VIDEO & HOOK ANGLE
3. CLIENT PITCH POSITIONING STATEMENT

Under the first heading: name the palette to use, the competitor colors to leave alone, and where the visual whitespace is.
Under the second heading: give one winning 3-second hook, then a four-block script labeled Hook, Customer Friction, Core Value, and Call to Action.
Under the third heading: one sentence only. It is the line for the client presentation deck.
"""


def compose_context(region_label: str, timeframe: str, visuals: list[dict], hooks: list[dict], domains: list[dict]) -> str:
    color_lines = []
    for row in visuals[:4]:
        hexes = ", ".join(row.get("hex_codes") or [])
        color_lines.append(
            f"- {row.get('ad_format')} ({row.get('active_days')} active days, {row.get('source')}): {hexes}. {row.get('insight')}"
        )
    hook_lines = []
    for row in hooks[:4]:
        script = row.get("script_structure") or {}
        hook_lines.append(
            "\n".join(
                [
                    f"- [{row.get('archetype')} / {row.get('engagement_tier')} / {row.get('source')}] {row.get('hook_text')}",
                    f"  Customer friction: {script.get('friction', '')}",
                    f"  Core value: {script.get('value', '')}",
                    f"  Call to action: {script.get('cta', '')}",
                ]
            )
        )
    rank_lines = []
    for row in domains[:6]:
        change = row.get("rank_change")
        movement = "new snapshot" if change is None else f"change {int(change):+d}"
        rank_lines.append(
            f"- {row.get('target_keyword')} — {row.get('domain_name')} at position {row.get('rank_position')} ({movement}, {row.get('source')})"
        )
    return "\n".join(
        [
            f"Region on the desk: {region_label}",
            f"Window: {timeframe}",
            "",
            "Color and format evidence:",
            "\n".join(color_lines) or "- None in this window.",
            "",
            "Opening hooks:",
            "\n".join(hook_lines) or "- None in this window.",
            "",
            "Search positions:",
            "\n".join(rank_lines) or "- None in this window.",
        ]
    )


def _content_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()
    return ""


def _complete(model: str, brief: str, context: str) -> dict:
    user = (
        f"Client brief:\n{brief.strip()}\n\n"
        f"Regional evidence currently on the desk:\n{context}\n\n"
        "Write the three sections for the client meeting."
    )
    try:
        response = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.7,
                "max_tokens": 1600,
                "thinking": {"type": "disabled"},
                "stream": False,
            },
            timeout=70,
        )
    except requests.Timeout:
        return {"ok": False, "text": "", "model": model, "error": "The strategist timed out.", "retry": False}
    except requests.RequestException:
        return {"ok": False, "text": "", "model": model, "error": "The strategist did not respond.", "retry": True}
    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            body = {}
        raw = ""
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                raw = str(error.get("message") or "")
            elif isinstance(error, str):
                raw = error
            raw = raw or str(body.get("message") or "")
        if response.status_code in {401, 403}:
            raw = raw or "The DeepSeek key was declined."
        elif response.status_code == 402:
            raw = raw or "The DeepSeek account has no remaining balance."
        elif response.status_code == 429:
            raw = raw or "DeepSeek is rate limiting this desk."
        else:
            raw = raw or f"DeepSeek failed ({response.status_code})."
        retry = response.status_code in {400, 404, 500, 502, 503}
        return {"ok": False, "text": "", "model": model, "error": scrub(raw)[:220], "retry": retry}
    try:
        body = response.json()
    except ValueError:
        return {"ok": False, "text": "", "model": model, "error": "The strategist returned an unreadable response.", "retry": False}
    choices = body.get("choices") if isinstance(body, dict) else None
    if not choices:
        return {"ok": False, "text": "", "model": model, "error": "The strategist returned no proposal.", "retry": True}
    text = _content_text(choices[0].get("message") or {})
    if not text:
        return {"ok": False, "text": "", "model": model, "error": "The strategist returned an empty proposal.", "retry": True}
    return {"ok": True, "text": text, "model": model, "error": "", "retry": False}


def propose(brief: str, context: str) -> dict:
    if not DEEPSEEK_API_KEY:
        return {"ok": False, "text": "", "model": "", "error": "DeepSeek key is not configured."}
    if not brief.strip():
        return {"ok": False, "text": "", "model": "", "error": "Write the client brief first."}
    last_error = "The strategist did not answer."
    for model in DEEPSEEK_MODELS:
        result = _complete(model, brief[:4000], context)
        if result["ok"]:
            return {"ok": True, "text": result["text"], "model": result["model"], "error": ""}
        last_error = result["error"]
        if not result.get("retry"):
            break
    return {"ok": False, "text": "", "model": "", "error": last_error}
