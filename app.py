"""diArtis Studio strategic war room."""

from __future__ import annotations

import inspect
import re
from datetime import datetime, timezone
from html import escape
from textwrap import dedent

import streamlit as st

from config import LABEL_TO_REGION, REGIONS, TIMEFRAMES, scrub
from data.db import (
    fetch_domains,
    fetch_hooks,
    fetch_radar,
    fetch_visuals,
    init_db,
    insert_proposal,
    latest_cache_time,
    parse_timestamp,
    recent_proposals,
)
from seed_data import seed_if_empty
from services.deepseek_copilot import compose_context, propose
from services.color_extractor import safe_hex
from services.apify_scraper import refresh_region as refresh_hooks
from services.serp_monitor import refresh_region as refresh_search

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&family=Playfair+Display:ital,wght@0,500;0,600;1,500&display=swap');

.stApp {
  background: #F8F8F5;
  color: #1A1A1A;
  font-family: "Outfit", "Segoe UI", sans-serif;
}
section.main > div.block-container {
  max-width: 1120px !important;
  padding-top: 2.2rem !important;
  padding-bottom: 3.5rem !important;
}
header[data-testid="stHeader"] { background: transparent; pointer-events: none; }
[data-testid="stDecoration"], [data-testid="stToolbar"], #MainMenu, footer { display: none; }
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp li {
  font-family: "Outfit", "Segoe UI", sans-serif;
}
.masthead { border-bottom: 1px solid #E2E2DC; padding-bottom: 1.15rem; margin-bottom: 0.2rem; }
.eyebrow, .filter-label, .micro, .footer {
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8C947D;
  font-weight: 500;
}
.masthead h1, .section-head h2, .card h3, .hook-line, .pitch-line, .serif {
  font-family: "Playfair Display", Georgia, "Times New Roman", serif;
  font-weight: 500;
  color: #4C5539;
  letter-spacing: -0.025em;
}
.masthead h1 { font-size: 46px; line-height: 1.02; margin: 0.15rem 0 0.4rem; }
.deck, .section-head p, .note { color: #666666; }
.deck { font-size: 16px; line-height: 1.45; margin: 0; max-width: 42rem; }
.filter-label { margin: 0.85rem 0 0.35rem; }
.inventory, .cached { font-size: 13px; color: #666666; margin: 0.35rem 0 0.7rem; }
.section-head { margin: 0.35rem 0 0.9rem; }
.section-head h2 { font-size: 32px; line-height: 1.08; margin: 0 0 0.28rem; }
.section-head p { margin: 0; font-size: 15px; }
.card {
  background: #FFFFFF;
  border: 1px solid #E2E2DC;
  padding: 20px 22px;
  margin: 0 0 16px;
}
.card h3 { font-size: 26px; line-height: 1.15; margin: 0.1rem 0 0.55rem; }
.card p { margin: 0; }
.stack { display: flex; flex-direction: column; gap: 16px; }
.grid-2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; align-items: stretch; }
.grid-2 .card { margin: 0; height: 100%; box-sizing: border-box; }
.facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 22px; margin-top: 4px; }
.fact { min-width: 0; }
.fact-value { display: block; margin-top: 4px; font-size: 15px; line-height: 1.4; color: #1A1A1A; }
.hook-line { font-size: 28px; line-height: 1.25; margin: 0.35rem 0 0.8rem; }
.strategy { font-size: 15px; line-height: 1.5; color: #1A1A1A; margin-top: 12px !important; }
.why { font-size: 13px; line-height: 1.5; color: #666666; margin-top: 10px !important; }
.badge-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.badge, .source-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.badge-hot { background: #4C5539; color: #F8F8F5; }
.badge-quiet { background: #FFFFFF; color: #1A1A1A; border: 1px solid #E2E2DC; }
.source-badge { background: #EFEFED; border: 1px solid #E2E2DC; color: #555555; font-weight: 500; }
.spectrum { display: flex; gap: 10px; margin-top: 8px; }
.swatch { flex: 1; min-width: 0; }
.band { height: 52px; border: 1px solid #E2E2DC; }
.hex { display: block; margin-top: 6px; font-size: 12px; letter-spacing: 0.04em; color: #1A1A1A; }
.radar-meta { display: flex; justify-content: space-between; gap: 12px; margin-top: 8px; font-size: 12px; color: #1A1A1A; }
.radar-track { display: flex; height: 16px; border: 1px solid #E2E2DC; margin-top: 8px; background: #F8F8F5; }
.radar-fill { height: 100%; }
.radar-gap { height: 100%; background: repeating-linear-gradient(-45deg, #F8F8F5, #F8F8F5 4px, #E2E2DC 4px, #E2E2DC 8px); }
.beats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
.beat { border-top: 1px solid #E2E2DC; padding-top: 10px; }
.beat p { font-size: 14px; line-height: 1.45; margin-top: 6px !important; color: #1A1A1A; }
.pitch-line, .pitch-line p {
  font-family: "Playfair Display", Georgia, serif;
  font-size: 26px;
  line-height: 1.35;
  color: #4C5539;
}
.footer { margin-top: 2.2rem; padding-top: 0.85rem; border-top: 1px solid #E2E2DC; }
div[data-testid="stRadio"] [role="radiogroup"] { display: flex; flex-wrap: wrap; gap: 8px; }
[data-testid="stRadioOption"] {
  background: #FFFFFF !important;
  color: #1A1A1A !important;
  border: 1px solid #E2E2DC !important;
  border-radius: 999px !important;
  padding: 0.42rem 0.95rem !important;
  margin: 0 !important;
  font-weight: 400;
  transition: background 0.15s ease, color 0.15s ease;
}
[data-testid="stRadioOption"] > div > div:first-child { display: none !important; }
[data-testid="stRadioOption"]:hover { background: #F0F0EC !important; }
[data-testid="stRadioOption"][data-selected="true"],
[data-testid="stRadioOption"]:has(input:checked) {
  background: #4C5539 !important;
  color: #F8F8F5 !important;
  border: 1px solid #4C5539 !important;
  font-weight: 500;
}
[data-testid="stRadioOption"][data-selected="true"]:hover,
[data-testid="stRadioOption"]:has(input:checked):hover { background: #4C5539 !important; }
[data-testid="stRadioOption"] p { margin: 0; font-size: 13px; color: inherit !important; font-weight: inherit; }
[data-testid="stTextAreaRootElement"] {
  background: #FFFFFF !important;
  border: 1px solid #E2E2DC !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}
[data-testid="stTextAreaRootElement"]:focus-within { border-color: #4C5539 !important; box-shadow: none !important; }
[data-testid="stTextArea"] textarea {
  background: transparent !important;
  border: none !important;
  color: #1A1A1A !important;
  box-shadow: none !important;
}
[data-testid="stHeadingWithActionElements"] a,
[data-testid="stHeaderActionElements"] { display: none !important; }
[data-testid="stWidgetLabel"] p { font-size: 11px !important; color: #666666 !important; }
.stApp button {
  border-radius: 999px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 12px;
  font-weight: 500;
  box-shadow: none;
}
.stApp button[kind="primary"], .stApp button[data-testid="stBaseButton-primary"] {
  background: #4C5539;
  color: #F8F8F5;
  border: 1px solid #4C5539;
}
.stApp button[kind="secondary"], .stApp button[data-testid="stBaseButton-secondary"] {
  background: #FFFFFF;
  color: #1A1A1A;
  border: 1px solid #E2E2DC;
}
.stApp button:focus { box-shadow: none !important; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: none; flex-wrap: wrap; }
.stTabs [data-baseweb="tab"],
[data-testid="stTab"] {
  background: #FFFFFF;
  color: #1A1A1A;
  border: 1px solid #E2E2DC;
  border-radius: 999px;
  height: auto;
  padding: 0.48rem 0.95rem;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.01em;
  text-transform: none;
}
.stTabs [data-baseweb="tab"]:hover,
[data-testid="stTab"]:hover { background: #F0F0EC; }
.stTabs [aria-selected="true"],
[data-testid="stTab"][aria-selected="true"] {
  background: #4C5539 !important;
  color: #F8F8F5 !important;
  border: 1px solid #4C5539 !important;
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display: none; }
[data-testid="stExpander"] details { background: #FFFFFF; border: 1px solid #E2E2DC; border-radius: 0; }
@media (max-width: 860px) {
  .grid-2, .facts, .beats { grid-template-columns: 1fr; }
  .masthead h1 { font-size: 34px; }
  .hook-line { font-size: 24px; }
}
"""

_HEADING = re.compile(
    r"(?im)^\s*(?:#{1,3}\s*)?("
    r"1\.\s*VISUAL DIRECTION[^\n]*|"
    r"2\.\s*(?:CONTENT|SHORT-FORM)[^\n]*|"
    r"3\.\s*(?:POSITIONING|CLIENT PITCH)[^\n]*"
    r")\s*$"
)
_BOLD = re.compile(r"(\*\*[^*]+\*\*)")

_BEATS = (
    ("01", "Hook", "hook"),
    ("02", "Friction", "friction"),
    ("03", "Core Value", "value"),
    ("04", "Call to Action", "cta"),
)

_SOURCES = {
    "STUDIO BASELINE": "Studio baseline",
    "SERPER API": "Live Google results",
    "APIFY TIKTOK": "Live short-form",
    "DEEPSEEK": "DeepSeek",
}


def esc(value) -> str:
    return escape("" if value is None else str(value)).replace("*", "&#42;").replace("_", "&#95;")


def show(fragment: str) -> None:
    fragment = dedent(str(fragment)).strip()
    if fragment:
        st.html(fragment)


def inject_css() -> None:
    st.html(f"<style>{CSS}</style>")


def press(label: str, key: str, *, primary: bool = False, help_text: str | None = None, disabled: bool = False) -> bool:
    kwargs = {"key": key, "disabled": disabled}
    if primary:
        kwargs["type"] = "primary"
    if help_text:
        kwargs["help"] = help_text
    names = set(inspect.signature(st.button).parameters)
    if "width" in names:
        kwargs["width"] = "content"
    return st.button(label, **kwargs)


def region_by_id(region_id: str) -> dict:
    for item in REGIONS:
        if item["id"] == region_id:
            return item
    return REGIONS[0]


def evidence(source: str | None) -> str:
    clean = _SOURCES.get(source or "", (source or "Studio baseline").title())
    return f"Evidence · {clean}"


def window_phrase(timeframe: str) -> str:
    return {
        "24 Hours": "the last 24 hours",
        "7 Days": "the last 7 days",
        "30 Days": "the last 30 days",
    }.get(timeframe, timeframe)


def cached_label(region_id: str) -> str:
    moment = latest_cache_time(region_id)
    if moment is None:
        return "Last cached: none yet"
    local = moment.astimezone()
    if local.date() == datetime.now().astimezone().date():
        return "Last cached: Today"
    return "Last cached: " + local.strftime("%d %b %Y")


def age_label(value: str) -> str:
    moment = parse_timestamp(value)
    if moment is None:
        return "Snapshot age: unknown"
    hours = max(0, int((datetime.now(timezone.utc) - moment).total_seconds() // 3600))
    if hours < 24:
        unit = "hour" if hours == 1 else "hours"
        return f"Snapshot age: {hours} {unit} ago"
    days = max(1, hours // 24)
    unit = "day" if days == 1 else "days"
    return f"Snapshot age: {days} {unit} ago"


def format_stamp(value: str) -> str:
    moment = parse_timestamp(value)
    if moment is None:
        return value or ""
    return moment.astimezone().strftime("%d %b %Y · %H:%M")


def stated(value, fallback: str) -> str:
    text = "" if value is None else str(value).strip()
    return text or fallback


def facts(pairs: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<div class="fact"><span class="micro">{esc(label)}</span>'
        f'<span class="fact-value">{esc(value)}</span></div>'
        for label, value in pairs
    )
    return f'<div class="facts">{cells}</div>'


def badge(signal: str) -> str:
    kind = "badge-hot" if "HIGH CONVERSION" in (signal or "").upper() else "badge-quiet"
    return f'<span class="badge {kind}">{esc(signal)}</span>'


def palette(colors: list[str]) -> str:
    blocks = []
    for color in (colors or [])[:5]:
        hx = safe_hex(color)
        blocks.append(
            f'<div class="swatch"><div class="band" style="background:{esc(hx)}"></div>'
            f'<span class="hex">{esc(hx)}</span></div>'
        )
    if not blocks:
        return '<p class="why">Color palette HEX: not in this snapshot.</p>'
    return (
        '<div class="micro" style="margin-top:16px">Color Palette HEX</div>'
        f'<div class="spectrum">{"".join(blocks)}</div>'
    )


def position_phrase(row: dict, timeframe: str) -> str:
    rank = f"Rank #{int(row.get('rank_position') or 0)}"
    movement = stated(row.get("movement_label"), "")
    if not movement:
        change = row.get("rank_change")
        if change is None:
            movement = "New in this snapshot"
        else:
            value = int(change)
            noun = "rank" if abs(value) == 1 else "ranks"
            if value > 0:
                movement = f"+{value} {noun} in {window_phrase(timeframe)}"
            elif value < 0:
                movement = f"{value} {noun} in {window_phrase(timeframe)}"
            else:
                movement = f"Holding the same rank in {window_phrase(timeframe)}"
    return f"{rank} ({movement})"


def domain_roles(rows: list[dict]) -> list[dict]:
    best: dict[str, int] = {}
    for row in rows:
        keyword = row.get("target_keyword") or ""
        position = int(row.get("rank_position") or 999)
        if keyword not in best or position < best[keyword]:
            best[keyword] = position
    labeled = []
    for row in rows:
        position = int(row.get("rank_position") or 999)
        role = "Top Ranking Domain" if position == best.get(row.get("target_keyword") or "") else "Competing Domain"
        labeled.append({**row, "domain_role": role})
    return sorted(labeled, key=lambda row: (row.get("target_keyword") or "", int(row.get("rank_position") or 999)))


def duration_signal(row: dict) -> str:
    signal = stated(row.get("signal"), "")
    if signal:
        return signal
    days = int(row.get("active_days") or 0)
    if days >= 30:
        return "HIGH CONVERSION SIGNAL — ROAS PROVEN"
    if days >= 14:
        return "HOLDING — SPEND STILL ON"
    return "SHORT RUN — NOT YET PROVEN"


def refresh_all(region_id: str) -> str:
    search = refresh_search(region_id)
    clips = refresh_hooks(region_id)
    return f"{search['message']} {clips['message']}"


def split_proposal(text: str) -> list[tuple[str, str]]:
    matches = list(_HEADING.finditer(text or ""))
    if not matches:
        return [("Strategic proposal", (text or "").strip())]
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = re.sub(r"^\d+\.\s*", "", match.group(1).strip())
        sections.append((title.title(), text[match.end() : end].strip()))
    return sections


def rich(text: str) -> str:
    parts = []
    for piece in _BOLD.split(text or ""):
        if piece.startswith("**") and piece.endswith("**") and len(piece) > 4:
            parts.append("<strong>" + esc(piece[2:-2]) + "</strong>")
        else:
            parts.append(esc(piece))
    merged = "".join(parts).strip()
    blocks = [block.strip() for block in re.split(r"\n\s*\n", merged) if block.strip()]
    if not blocks:
        return ""
    return "".join("<p>" + "<br>".join(block.split("\n")) + "</p>" for block in blocks)


def tally(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def empty_card(title: str, detail: str) -> str:
    return (
        f'<div class="card"><h3>{esc(title)}</h3><p class="why">{esc(detail)}</p></div>'
    )


def render_masthead() -> None:
    show(
        """
        <div class="masthead">
          <p class="eyebrow">diArtis Studio · Internal desk</p>
          <h1>Strategic War Room</h1>
          <p class="deck">Social spy, ad creative, and search intelligence. Choose a geography and a timeframe and every card reloads for that window.</p>
        </div>
        """
    )


def render_controls() -> tuple[str, str]:
    labels = [item["label"] for item in REGIONS]
    show('<p class="filter-label">Geography</p>')
    selected = st.radio(
        "Geography",
        labels,
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        key="region_label",
    )
    show('<p class="filter-label">Timeframe</p>')
    timeframe = st.radio(
        "Timeframe",
        list(TIMEFRAMES),
        index=2,
        horizontal=True,
        label_visibility="collapsed",
        key="timeframe",
    )
    region_id = LABEL_TO_REGION[selected]["id"]
    show(f'<p class="cached">{esc(cached_label(region_id))}</p>')
    if press(
        "Fetch Latest Intel",
        key="refresh",
        help_text="Reads live search positions and public short-form clips. Cached cards stay in place if a source is quiet.",
    ):
        with st.spinner("Reading live search positions and public clips…"):
            st.session_state["refresh_report"] = {"region": region_id, "text": refresh_all(region_id)}
    report = st.session_state.get("refresh_report")
    if report and report.get("region") == region_id:
        show(f'<p class="why">{esc(report.get("text"))}</p>')
    return region_id, timeframe


def render_ads(region: dict, timeframe: str, visuals: list[dict], radar: list[dict]) -> None:
    show(
        f"""
        <div class="section-head">
          <h2>Social &amp; Meta Ad Spy</h2>
          <p>{esc(region["short"])} · {esc(timeframe)}. Active competitor ads, how long they have been spending, and the colors this market has left open.</p>
        </div>
        """
    )
    if not visuals:
        show(empty_card(
            "No active ads in this window",
            "Widen the timeframe to 7 Days or 30 Days, or fetch the latest intel.",
        ))
    else:
        cards = []
        for row in visuals:
            days = int(row.get("active_days") or 0)
            note = stated(row.get("strategy_note") or row.get("insight"), "No strategy note in this snapshot.")
            body = facts(
                [
                    ("Brand / Competitor", stated(row.get("brand_name"), "Competitor not named")),
                    ("Niche", stated(row.get("niche"), "Niche not named")),
                    ("Ad Format", stated(row.get("ad_format"), "Format not named")),
                    ("Duration Active", f"{days} Days"),
                    ("Snapshot", age_label(row.get("timestamp") or "")),
                    ("Timeframe", timeframe),
                ]
            )
            cards.append(
                f"""
                <div class="card">
                  <p class="micro">Active Ad Endurance</p>
                  <h3>{esc(stated(row.get("brand_name"), row.get("ad_format")))}</h3>
                  {body}
                  {palette(row.get("hex_codes") or [])}
                  <p class="strategy"><span class="micro">Visual Strategy Note</span><br>{esc(note)}</p>
                  <div class="badge-row">
                    {badge(duration_signal(row))}
                    <span class="source-badge">{esc(evidence(row.get("source")))}</span>
                  </div>
                </div>
                """
            )
        show('<div class="stack">' + "".join(cards) + "</div>")

    show('<h3 class="serif" style="font-size:28px;margin:0.6rem 0 0.7rem;">Regional Color Whitespace Radar</h3>')
    if not radar:
        show(empty_card(
            "No color reading in this window",
            "Widen the timeframe. The radar names the crowded color and the open one.",
        ))
        return
    blocks = []
    for row in radar:
        pct = max(0, min(100, int(row.get("saturation_pct") or 0)))
        gap = 100 - pct
        hx = safe_hex(row.get("dominant_hex") or "")
        blocks.append(
            f"""
            <div class="card">
              <p class="micro">Color Saturation</p>
              <h3>{esc(row.get("niche"))}</h3>
              {facts([
                  ("Dominant Color", f"{row.get('color_name')} ({hx})"),
                  ("Share of the niche", f"{pct}% of visible ads"),
                  ("Visual whitespace left", f"{gap}% of the frame"),
                  ("Snapshot", age_label(row.get("timestamp") or "")),
              ])}
              <div class="radar-track" role="img" aria-label="{esc(pct)} percent {esc(row.get('color_name'))}, {esc(gap)} percent open">
                <div class="radar-fill" style="width:{pct}%;background:{esc(hx)}"></div>
                <div class="radar-gap" style="width:{gap}%"></div>
              </div>
              <div class="radar-meta"><span>{esc(pct)}% crowded</span><span>{esc(gap)}% open</span></div>
              <p class="strategy"><span class="micro">Whitespace Opening</span><br>{esc(row.get("whitespace_note"))}</p>
              <div class="badge-row"><span class="source-badge">{esc(evidence(row.get("source")))}</span></div>
            </div>
            """
        )
    show('<div class="stack">' + "".join(blocks) + "</div>")


def render_hooks(region: dict, timeframe: str, hooks: list[dict]) -> None:
    show(
        f"""
        <div class="section-head">
          <h2>Viral Short-Form Engine</h2>
          <p>{esc(region["short"])} · {esc(timeframe)}. Opening lines with view counts, cut pace, and the four beats of the script.</p>
        </div>
        """
    )
    if not hooks:
        show(empty_card(
            "No spoken hooks in this window",
            "Widen the timeframe, or fetch the latest public clips.",
        ))
        return
    cards = []
    for row in hooks:
        script = row.get("script_structure") if isinstance(row.get("script_structure"), dict) else {}
        views = stated(row.get("views_label"), stated(row.get("engagement_tier"), "Views not stated"))
        pace = stated(row.get("pace_label"), "Cut pace not stated")
        beats = []
        for number, label, key in _BEATS:
            text = stated(script.get(key), "Not captured in this clip")
            beats.append(
                f'<div class="beat"><span class="micro">{esc(number)} · {esc(label)}</span><p>{esc(text)}</p></div>'
            )
        cards.append(
            f"""
            <div class="card">
              <p class="micro">Opening Hook</p>
              <p class="hook-line">{esc(row.get("hook_text"))}</p>
              {facts([
                  ("Performance Metric", f"{views} · {pace}"),
                  ("Archetype", stated(row.get("archetype"), "Archetype not named")),
                  ("Engagement Tier", stated(row.get("engagement_tier"), "Tier not stated")),
                  ("Snapshot", age_label(row.get("timestamp") or "")),
              ])}
              <div class="beats">{"".join(beats)}</div>
              <p class="why">{esc(stated(row.get("insight"), ""))}</p>
              <div class="badge-row"><span class="source-badge">{esc(evidence(row.get("source")))}</span></div>
            </div>
            """
        )
    show('<div class="stack">' + "".join(cards) + "</div>")


def render_search(region: dict, timeframe: str, domains: list[dict]) -> None:
    show(
        f"""
        <div class="section-head">
          <h2>Search Velocity &amp; Competitor Radar</h2>
          <p>{esc(region["short"])} · {esc(timeframe)}. Google position, traffic, search spikes, and the question sitting in the comments.</p>
        </div>
        """
    )
    if not domains:
        show(empty_card(
            "No search positions in this window",
            "Widen the timeframe, or fetch the latest Google results.",
        ))
        return
    cards = []
    for row in domain_roles(domains):
        share = stated(row.get("objection_share"), "")
        where = stated(row.get("objection_where"), "the comment threads")
        question = stated(row.get("objection_text"), "")
        if share and question:
            objection = f"{share} of audience comments under {where} ask: {question}"
        elif question:
            objection = question
        else:
            objection = "No comment sample in this snapshot."
        cards.append(
            f"""
            <div class="card">
              <p class="micro">Search Position</p>
              <h3>{esc(row.get("target_keyword"))}</h3>
              {facts([
                  ("Target Search Query", stated(row.get("target_keyword"), "Query not named")),
                  (row.get("domain_role") or "Domain", stated(row.get("domain_name"), "Domain not named")),
                  ("Monthly Traffic Volume", stated(row.get("monthly_traffic"), "Not in this snapshot")),
                  ("Current Google Position", position_phrase(row, timeframe)),
                  ("Search Volume Status", stated(row.get("search_status"), "No spike recorded in this snapshot")),
                  ("Snapshot", age_label(row.get("timestamp") or "")),
              ])}
              <p class="strategy"><span class="micro">Strategic Insight</span><br>{esc(stated(row.get("insight"), "No strategic note in this snapshot."))}</p>
              <p class="strategy"><span class="micro">Customer Objection</span><br>{esc(objection)}</p>
              <div class="badge-row"><span class="source-badge">{esc(evidence(row.get("source")))}</span></div>
            </div>
            """
        )
    show('<div class="stack">' + "".join(cards) + "</div>")


def render_proposal(text: str, source: str) -> None:
    blocks = []
    for title, body in split_proposal(text):
        body_html = rich(body)
        if "positioning" in title.lower():
            body_html = f'<div class="pitch-line">{body_html}</div>'
        blocks.append(
            f"""
            <div class="card">
              <p class="micro">Proposal section</p>
              <h3>{esc(title)}</h3>
              {body_html}
              <div class="badge-row"><span class="source-badge">{esc(evidence(source))}</span></div>
            </div>
            """
        )
    show('<div class="stack">' + "".join(blocks) + "</div>")


def render_strategy(
    region: dict,
    timeframe: str,
    visuals: list[dict],
    radar: list[dict],
    hooks: list[dict],
    domains: list[dict],
) -> None:
    show(
        f"""
        <div class="section-head">
          <h2>Studio Strategic Assistant</h2>
          <p>Diana writes the client request. The copilot answers from {esc(region["short"])} and {esc(timeframe)} only, in three parts: Visual Direction, Content and Hook Strategy, Positioning Statement.</p>
        </div>
        """
    )
    show(
        f"""
        <p class="inventory">Evidence on the desk: {tally(len(visuals), "active ad", "active ads")}, {tally(len(radar), "color reading", "color readings")}, {tally(len(hooks), "hook", "hooks")}, {tally(len(domains), "search position", "search positions")}. Geography {esc(region["short"])}. Timeframe {esc(timeframe)}.</p>
        """
    )
    brief = st.text_area(
        "Client request",
        height=150,
        placeholder="Varna dental clinic launching high-end veneers. Needs a brand system and a 30-day ad campaign.",
        key="client_brief",
    )
    if press("Generate Strategic Proposal", key="generate", primary=True, disabled=not brief.strip()):
        context = compose_context(region["label"], timeframe, visuals, hooks, domains, radar)
        with st.spinner("Composing the three-part pitch…"):
            result = propose(brief, context)
        st.session_state["proposal"] = {
            "region": region["id"],
            "timeframe": timeframe,
            "brief": brief.strip(),
            "ok": result["ok"],
            "text": result.get("text") or "",
            "error": result.get("error") or "",
            "model": result.get("model") or "",
        }
        if result["ok"]:
            insert_proposal(region["id"], brief.strip(), result["text"])
    proposal = st.session_state.get("proposal")
    if proposal and proposal.get("region") == region["id"] and proposal.get("timeframe") == timeframe:
        if proposal.get("ok") and proposal.get("text"):
            source = "DEEPSEEK"
            if proposal.get("model"):
                source = f"DEEPSEEK · {proposal['model']}"
            render_proposal(proposal["text"], source)
        elif proposal.get("error"):
            show(empty_card("The strategist did not answer", proposal.get("error") or ""))
    history = recent_proposals(region["id"], timeframe, limit=5)
    current_text = ""
    if proposal and proposal.get("region") == region["id"] and proposal.get("timeframe") == timeframe:
        current_text = proposal.get("text") or ""
    older = [row for row in history if row.get("generated_proposal") != current_text]
    if older:
        with st.expander("Previous proposals in this window"):
            for row in older:
                show(
                    f"""
                    <div class="card">
                      <p class="micro">{esc(format_stamp(row.get("timestamp")))}</p>
                      <p class="fact-value" style="margin-top:8px">{esc(row.get("client_brief"))}</p>
                    </div>
                    """
                )
                render_proposal(row.get("generated_proposal") or "", "DEEPSEEK")


def render_desk() -> None:
    render_masthead()
    region_id, timeframe = render_controls()
    region = region_by_id(region_id)
    visuals = fetch_visuals(region_id, timeframe)
    radar = fetch_radar(region_id, timeframe)
    hooks = fetch_hooks(region_id, timeframe)
    domains = fetch_domains(region_id, timeframe)
    show(
        f"""
        <p class="inventory">{esc(region["short"])} · {esc(timeframe)} · {tally(len(visuals), "active ad", "active ads")} · {tally(len(radar), "color reading", "color readings")} · {tally(len(hooks), "hook", "hooks")} · {tally(len(domains), "search position", "search positions")}</p>
        """
    )
    ad_tab, hook_tab, search_tab, strategy_tab = st.tabs(
        ["Social & Meta Ad Spy", "Viral Short-Form", "Search Velocity", "Strategic Assistant"]
    )
    with ad_tab:
        render_ads(region, timeframe, visuals, radar)
    with hook_tab:
        render_hooks(region, timeframe, hooks)
    with search_tab:
        render_search(region, timeframe, domains)
    with strategy_tab:
        render_strategy(region, timeframe, visuals, radar, hooks, domains)
    show('<p class="footer">diArtis Studio · Strategic War Room · For pitch preparation</p>')


def main() -> None:
    st.set_page_config(
        page_title="diArtis Studio — Strategic War Room",
        page_icon="◆",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_css()
    try:
        init_db()
        seed_if_empty()
    except Exception as exc:
        show(empty_card("The local cache did not open", scrub(str(exc))[:240]))
        return
    render_desk()


main()
