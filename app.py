"""diArtis Studio market intelligence desk."""

from __future__ import annotations

import inspect
import re
from datetime import datetime
from html import escape
from textwrap import dedent

import streamlit as st

from config import (
    BRAND_PALETTE,
    LABEL_TO_REGION,
    REGIONS,
    SOURCE_BRAND,
    TIMEFRAMES,
    scrub,
)
from data.db import (
    fetch_domains,
    fetch_hooks,
    fetch_visuals,
    init_db,
    insert_proposal,
    latest_cache_time,
    parse_timestamp,
    recent_proposals,
)
from seed_data import seed_if_empty
from services.apify_scraper import refresh_region as refresh_hooks
from services.color_extractor import extract_from_bytes, extract_from_url, safe_hex
from services.deepseek_copilot import compose_context, propose
from services.serp_monitor import refresh_region as refresh_search
from services.tech_detector import inspect_url

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500&family=Playfair+Display:ital,wght@0,500;0,600;1,500&display=swap');

.stApp {
  background: #F8F8F5;
  color: #1A1A1A;
  font-family: "Outfit", "Segoe UI", sans-serif;
}
section.main > div.block-container {
  max-width: 1080px !important;
  padding-top: 2.4rem !important;
  padding-bottom: 3.5rem !important;
}
header[data-testid="stHeader"] {
  background: transparent;
  pointer-events: none;
}
[data-testid="stDecoration"], [data-testid="stToolbar"], #MainMenu, footer { display: none; }
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp li {
  font-family: "Outfit", "Segoe UI", sans-serif;
}
.masthead { border-bottom: 1px solid #E2E2DC; padding-bottom: 1.25rem; margin-bottom: 0.4rem; }
.eyebrow, .filter-label, .kicker, .tier, .source-badge, .footer {
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8C947D;
}
.eyebrow, .filter-label, .kicker, .tier { letter-spacing: 0.14em; }
.masthead h1, .section-head h2, .card h3, .quote, .position, .pace-num, .pitch-line, .serif {
  font-family: "Playfair Display", Georgia, "Times New Roman", serif;
  font-weight: 500;
  color: #4C5539;
  letter-spacing: -0.025em;
}
.masthead h1 { font-size: 46px; line-height: 1.02; margin: 0.2rem 0 0.45rem; }
.deck, .section-head p, .note { color: #666666; }
.deck { font-size: 16px; line-height: 1.45; margin: 0; max-width: 40rem; }
.filter-label { margin: 0.9rem 0 0.2rem; }
.cached { font-size: 12px; color: #666666; text-align: left; margin: 0.85rem 0 0.45rem; }
.section-head { margin: 0.6rem 0 0.8rem; }
.section-head h2 { font-size: 34px; line-height: 1.05; margin: 0 0 0.3rem; }
.section-head p { margin: 0; font-size: 15px; }
.card {
  background: #FFFFFF;
  border: 1px solid #E2E2DC;
  padding: 20px;
  margin: 0 0 16px;
}
.card h3 { font-size: 26px; line-height: 1.15; margin: 0.15rem 0 0.4rem; }
.card p { margin: 0; }
.card-top, .rank, .pace-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 18px; }
.quote { font-size: 30px; line-height: 1.22; margin: 0.45rem 0 0.15rem; overflow-wrap: anywhere; }
.why { font-size: 11px; line-height: 1.5; color: #666666; margin-top: 8px !important; }
.source-badge {
  display: inline-block;
  margin-top: 14px;
  background: #EFEFED;
  border: 1px solid #E2E2DC;
  color: #555555;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 4px 8px;
  border-radius: 4px;
}
.meta-line { font-size: 14px; line-height: 1.45; color: #1A1A1A; margin-top: 0.35rem !important; }
.note { font-size: 13px; line-height: 1.45; margin-top: 0.2rem !important; }
.position { font-size: 46px; line-height: 0.85; }
.pace-num { font-size: 42px; line-height: 0.9; }
.pitch-line, .pitch-line p {
  font-family: "Playfair Display", Georgia, serif;
  font-size: 28px;
  line-height: 1.35;
  color: #4C5539;
}
.beats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 16px; }
.beats p { font-size: 14px; line-height: 1.45; margin-top: 6px !important; color: #1A1A1A; }
.grid-3, .grid-2 { display: grid; gap: 16px; align-items: stretch; }
.grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid-3 .card, .grid-2 .card { margin: 0; height: 100%; box-sizing: border-box; }
.tag {
  display: inline-block;
  border: 1px solid #E2E2DC;
  color: #4C5539;
  font-size: 12px;
  letter-spacing: 0.05em;
  padding: 6px 10px;
  margin: 0 8px 8px 0;
}
.footer { margin-top: 2.2rem; padding-top: 0.85rem; border-top: 1px solid #E2E2DC; }
.center { text-align: center; }
div[data-testid="stRadio"] [role="radiogroup"] { display: flex; flex-wrap: wrap; gap: 8px; }
[data-testid="stRadioOption"] {
  background: #FFFFFF !important;
  color: #1A1A1A !important;
  border: 1px solid #E2E2DC !important;
  border-radius: 4px !important;
  padding: 0.42rem 0.8rem !important;
  margin: 0 !important;
  font-weight: 400;
  transition: background 0.15s ease;
}
[data-testid="stRadioOption"] > div > div:first-child { display: none !important; }
[data-testid="stRadioOption"]:hover { background: #F0F0EC !important; }
[data-testid="stRadioOption"][data-selected="true"] {
  background: #4C5539 !important;
  color: #F8F8F5 !important;
  border: 1px solid #4C5539 !important;
  font-weight: 500;
}
[data-testid="stRadioOption"][data-selected="true"]:hover { background: #4C5539 !important; }
[data-testid="stRadioOption"] p { margin: 0; font-size: 13px; color: inherit !important; font-weight: inherit; }
[data-testid="stTextInputRootElement"],
[data-testid="stTextAreaRootElement"] {
  background: #FFFFFF !important;
  border: 1px solid #E2E2DC !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}
[data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stTextAreaRootElement"]:focus-within {
  border-color: #4C5539 !important;
  box-shadow: none !important;
}
[data-testid="stTextInputField"],
[data-testid="stTextArea"] textarea {
  background: transparent !important;
  border: none !important;
  border-radius: 0 !important;
  color: #1A1A1A !important;
  box-shadow: none !important;
}
[data-testid="stHeadingWithActionElements"] a,
[data-testid="stHeaderActionElements"] { display: none !important; }
[data-testid="stFileUploaderDropzoneInstructions"] { display: none !important; }
[data-testid="stWidgetLabel"] p { font-size: 11px !important; color: #666666 !important; }
.stApp button {
  border-radius: 4px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 12px;
  font-weight: 500;
  box-shadow: none;
  transition: background 0.15s ease;
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
.stApp button[kind="secondary"]:hover, .stApp button[data-testid="stBaseButton-secondary"]:hover {
  background: #F0F0EC;
  border-color: #E2E2DC;
  color: #1A1A1A;
}
.stApp button:focus { box-shadow: none !important; }
.stTabs [data-baseweb="tab-list"] {
  gap: 8px;
  border-bottom: none;
}
.stTabs [data-baseweb="tab"],
[data-testid="stTab"] {
  background: #FFFFFF;
  color: #1A1A1A;
  border: 1px solid #E2E2DC;
  border-radius: 4px;
  height: auto;
  padding: 0.45rem 0.85rem;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
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
[data-testid="stFileUploader"] section {
  background: #FFFFFF;
  border: 1px solid #E2E2DC;
  border-radius: 0;
  padding: 0.6rem 0.8rem;
}
[data-testid="stExpander"] details {
  background: #FFFFFF;
  border: 1px solid #E2E2DC;
  border-radius: 0;
}
@media (max-width: 860px) {
  .grid-3, .grid-2, .beats { grid-template-columns: 1fr; }
  .masthead h1 { font-size: 34px; }
  .cached { text-align: left; }
  .quote { font-size: 26px; }
}
"""

_HEADING = re.compile(
    r"(?im)^\s*(?:#{1,3}\s*)?(1\.\s*VISUAL DIRECTION[^\n]*|2\.\s*SHORT-FORM[^\n]*|3\.\s*CLIENT PITCH[^\n]*)\s*$"
)
_BOLD = re.compile(r"(\*\*[^*]+\*\*)")
_BEATS = (
    ("01", "Hook", "hook"),
    ("02", "Customer Friction", "friction"),
    ("03", "Core Value", "value"),
    ("04", "Call to Action", "cta"),
)

_PALETTE_TEMPLATE = """<!DOCTYPE html>
<html><head>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500&family=Playfair+Display:wght@500&display=swap">
<style>
  html, body { margin: 0; background: transparent; font-family: Outfit, "Segoe UI", sans-serif; color: #1A1A1A; }
  .card { background: #fff; border: 1px solid #E2E2DC; padding: 20px; box-sizing: border-box; }
  .kicker, .hint { font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: #8C947D; }
  .source { display: inline-block; margin-top: 14px; background: #EFEFED; border: 1px solid #E2E2DC; color: #555555; font-size: 10px; font-weight: 500; letter-spacing: 0.12em; text-transform: uppercase; padding: 4px 8px; border-radius: 4px; }
  h3 { font-family: "Playfair Display", Georgia, serif; font-weight: 500; font-size: 26px; color: #4C5539; margin: 4px 0 6px; letter-spacing: -0.02em; }
  .note, .why { font-size: 11px; line-height: 1.5; color: #666; }
  .note { font-size: 13px; margin: 0 0 14px; }
  .why { margin: 12px 0 0; }
  .source { margin-top: 14px; }
  .spectrum { display: flex; gap: 10px; }
  .swatch { flex: 1; min-width: 0; }
  .band { height: 68px; border: 1px solid #E2E2DC; }
  button { width: 100%; margin-top: 8px; padding: 0; border: 0; background: transparent; text-align: left; cursor: pointer; font-family: inherit; }
  .hex { display: block; font-size: 12px; letter-spacing: 0.05em; color: #1A1A1A; }
  .hint { display: block; margin-top: 2px; }
</style></head>
<body><div class="card">
  <div class="kicker">__EYEBROW__</div>
  <h3>__TITLE__</h3>
  <p class="note">__NOTE__</p>
  <div class="spectrum">__SWATCHES__</div>
  <p class="why">__WHY__</p>
  <div class="source">Source · __SOURCE__</div>
</div>
<script>
function copyHex(value, btn) {
  var hint = btn.querySelector(".hint");
  function done(label) { hint.textContent = label; setTimeout(function () { hint.textContent = ""; }, 1200); }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(value).then(function () { done("Copied"); }, function () { done("Select HEX"); });
  } else { done("Select HEX"); }
}
</script>
</body></html>"""


def esc(value) -> str:
    return escape("" if value is None else str(value)).replace("*", "&#42;").replace("_", "&#95;")


def show(fragment: str) -> None:
    fragment = dedent(str(fragment)).strip()
    if fragment:
        st.html(fragment)


def embed_html(document: str) -> None:
    if hasattr(st, "iframe"):
        st.iframe(document, height="content", width="stretch")
        return
    import streamlit.components.v1 as components

    components.html(document, height=340, scrolling=False)


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


def cached_label(region_id: str) -> str:
    moment = latest_cache_time(region_id)
    if moment is None:
        return "Last cached: —"
    local = moment.astimezone()
    if local.date() == datetime.now().astimezone().date():
        return "Last cached: Today"
    return "Last cached: " + local.strftime("%d %b %Y")


def format_stamp(value: str) -> str:
    moment = parse_timestamp(value)
    if moment is None:
        return value or ""
    return moment.astimezone().strftime("%d %b %Y · %H:%M")


def duration_tag(days: int) -> str:
    days = int(days)
    if days >= 30:
        return f"Active {days} Days — high conversion signal"
    return f"Active {days} Days"


def movement_line(change) -> str:
    if change is None:
        return "New in this snapshot"
    value = int(change)
    if value == 0:
        return "Holding the same position as the previous snapshot"
    noun = "position" if abs(value) == 1 else "positions"
    if value > 0:
        return f"Up {value} {noun} since the previous snapshot"
    return f"Down {abs(value)} {noun} since the previous snapshot"


def balanced(rows: list[dict], keyfn, limit: int) -> list[dict]:
    groups: dict = {}
    order = []
    for row in rows:
        key = keyfn(row)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    output = []
    while len(output) < limit and any(groups[key] for key in order):
        for key in order:
            if groups[key]:
                output.append(groups[key].pop(0))
            if len(output) >= limit:
                break
    return output


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
        sections.append((match.group(1).strip(), text[match.end() : end].strip()))
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


def palette_frame(colors: list[str], eyebrow: str, title: str, note: str, why: str, source: str) -> None:
    swatches = []
    for color in colors[:5]:
        hx = safe_hex(color)
        swatches.append(
            f'<div class="swatch"><div class="band" style="background:{hx}"></div>'
            f'<button type="button" onclick="copyHex(\'{hx}\', this)">'
            f'<span class="hex">{hx}</span><span class="hint"></span></button></div>'
        )
    document = _PALETTE_TEMPLATE
    for token, value in (
        ("__EYEBROW__", esc(eyebrow)),
        ("__TITLE__", esc(title)),
        ("__NOTE__", esc(note)),
        ("__WHY__", esc(why)),
        ("__SOURCE__", esc(source)),
        ("__SWATCHES__", "".join(swatches)),
    ):
        document = document.replace(token, value)
    embed_html(document)


def render_masthead() -> None:
    show(
        """
        <div class="masthead">
          <p class="eyebrow">Varna · Internal desk</p>
          <h1>diArtis Studio — Market Intelligence</h1>
          <p class="deck">Regional trend analysis, visual radar &amp; strategic pitch co-pilot</p>
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


def render_visuals(region: dict, visuals: list[dict], domains: list[dict]) -> None:
    show(
        f"""
        <div class="section-head">
          <h2>Visual &amp; brand radar</h2>
          <p>{esc(region["short"])}. Competitor markup, the colors already taken, and the pages holding the click.</p>
        </div>
        """
    )
    show("<h3 class='serif' style='font-size:28px;margin:0.2rem 0 0.6rem;'>Competitor tech &amp; pixel audit</h3>")
    url = st.text_input("Competitor URL", placeholder="https://", key="audit_url", label_visibility="collapsed")
    run_audit = press("Read the page", key="audit_button")
    if run_audit:
        with st.spinner("Reading the public page…"):
            st.session_state["audit"] = inspect_url(url)
    audit = st.session_state.get("audit")
    if not audit:
        show(
            """
            <div class="card">
              <p class="note">Paste a competitor address. The scan reads public HTML, headers, and common pixels.</p>
              <p class="why">Pixels and the CMS tell you how demand is measured, and how heavy a rebuild will be. Pitch the measurement gap, not a shopping list of tools.</p>
              <span class="source-badge">Source · PUBLIC PAGE HEADERS</span>
            </div>
            """
        )
    elif not audit.get("ok"):
        show(
            f"""
            <div class="card">
              <h3>Page not read</h3>
              <p class="why">{esc(audit.get("error"))}</p>
              <span class="source-badge">Source · {esc(audit.get("source"))}</span>
            </div>
            """
        )
    else:
        tags = "".join(f'<span class="tag">{esc(tag)}</span>' for tag in audit.get("tags") or [])
        if not tags:
            tags = '<p class="note">No common marketing pixels, CMS platforms, or booking tools in the public HTML.</p>'
        notes = "".join(f'<p class="note">{esc(note)}</p>' for note in audit.get("notes") or [])
        show(
            f"""
            <div class="card">
              <div class="kicker">{esc(audit.get("final_url"))}</div>
              <div style="margin-top:12px">{tags}</div>
              {notes}
              <p class="why">Pixels and the CMS tell you how demand is measured, and how heavy a rebuild will be. Pitch the measurement gap, not a shopping list of tools.</p>
              <span class="source-badge">Source · {esc(audit.get("source"))}</span>
            </div>
            """
        )

    if visuals:
        lead = visuals[0]
        palette_frame(
            lead.get("hex_codes") or BRAND_PALETTE,
            "Regional palette",
            lead.get("ad_format") or "Color clusters",
            f"Most recent format in this window. {duration_tag(lead.get('active_days') or 0)}.",
            lead.get("insight") or "Dominant regional HEX clusters — use to spot visual whitespace.",
            lead.get("source") or "STUDIO BASELINE",
        )
    else:
        show(
            """
            <div class="card">
              <h3>No color clusters in this window</h3>
              <p class="why">Open 30 Days, or fetch the latest intel. Dominant regional HEX clusters — use to spot visual whitespace.</p>
              <span class="source-badge">Source · STUDIO BASELINE</span>
            </div>
            """
        )

    show("<h3 class='serif' style='font-size:28px;margin:0.4rem 0 0.55rem;'>Reference image</h3>")
    show('<p class="note" style="margin-top:-0.35rem;margin-bottom:0.6rem;">Cluster a still from their site or film. Five HEX values, ordered by share of the frame.</p>')
    image_url = st.text_input("Image address", placeholder="https://", key="image_url")
    extract = press("Extract palette", key="extract_palette")
    upload = st.file_uploader("Or a still from your machine", type=["png", "jpg", "jpeg", "webp"], key="image_file")
    if extract:
        if upload is not None:
            st.session_state["extracted"] = extract_from_bytes(upload.getvalue())
        elif image_url.strip():
            with st.spinner("Reading the image…"):
                st.session_state["extracted"] = extract_from_url(image_url.strip())
        else:
            st.session_state["extracted"] = {
                "ok": False,
                "colors": list(BRAND_PALETTE),
                "source": SOURCE_BRAND,
                "note": "Add an image address or a still. Showing the diArtis brand tones.",
            }
    extracted = st.session_state.get("extracted")
    if extracted:
        palette_frame(
            extracted.get("colors") or BRAND_PALETTE,
            "Reference image",
            "Extracted palette" if extracted.get("ok") else "Brand tones",
            extracted.get("note") or "",
            "Use the largest share as the ground. If it matches the regional palette, it is not whitespace.",
            extracted.get("source") or SOURCE_BRAND,
        )

    show("<h3 class='serif' style='font-size:28px;margin:0.3rem 0 0.7rem;'>Active creative formats</h3>")
    if not visuals:
        show('<div class="card"><p class="why">No active formats in this window.</p></div>')
    else:
        cards = []
        for row in visuals:
            cards.append(
                f"""
                <div class="card">
                  <div class="kicker">{esc(duration_tag(row.get("active_days") or 0))}</div>
                  <h3>{esc(row.get("ad_format"))}</h3>
                  <p class="why">{esc(row.get("insight"))}</p>
                  <span class="source-badge">Source · {esc(row.get("source"))}</span>
                </div>
                """
            )
        show('<div class="grid-3">' + "".join(cards) + "</div>")

    show("<h3 class='serif' style='font-size:28px;margin:1.1rem 0 0.7rem;'>Search position movement</h3>")
    ranked = balanced(domains, lambda row: row.get("target_keyword"), 6)
    if not ranked:
        show('<div class="card"><p class="why">No positions in this window. Widen the timeframe, or fetch the latest intel.</p></div>')
    else:
        cards = []
        for row in ranked:
            cards.append(
                f"""
                <div class="card">
                  <div class="rank">
                    <div>
                      <div class="kicker">{esc(row.get("target_keyword"))}</div>
                      <h3>{esc(row.get("domain_name"))}</h3>
                      <p class="meta-line">{esc(movement_line(row.get("rank_change")))}</p>
                      <p class="why">{esc(row.get("insight"))}</p>
                      <span class="source-badge">Source · {esc(row.get("source"))}</span>
                    </div>
                    <div class="position">{esc(row.get("rank_position"))}</div>
                  </div>
                </div>
                """
            )
        show('<div class="grid-2">' + "".join(cards) + "</div>")


def render_hooks(region: dict, timeframe: str, hooks: list[dict]) -> None:
    show(
        f"""
        <div class="section-head">
          <h2>Short-form hook engine</h2>
          <p>{esc(region["short"])} · {esc(timeframe)}. Opening lines, the four beats under them, and the pace of the cut.</p>
        </div>
        """
    )
    if not hooks:
        show(
            """
            <div class="card">
              <h3>No opening lines in this window</h3>
              <p class="why">Open 30 Days for the rehearsal set, or fetch the latest intel for public clips.</p>
              <span class="source-badge">Source · STUDIO BASELINE</span>
            </div>
            """
        )
        return
    cards = []
    for row in hooks[:4]:
        script = row.get("script_structure") or {}
        beats = []
        for number, label, key in _BEATS:
            beats.append(
                f"""
                <div>
                  <span class="kicker">{number} · {label}</span>
                  <p>{esc(script.get(key) or "Not stated.")}</p>
                </div>
                """
            )
        cards.append(
            f"""
            <div class="card">
              <div class="card-top">
                <span class="kicker">{esc(row.get("archetype"))}</span>
                <span class="tier">{esc(row.get("engagement_tier"))}</span>
              </div>
              <p class="quote">{esc(row.get("hook_text"))}</p>
              <div class="beats">{"".join(beats)}</div>
              <p class="why">{esc(row.get("insight"))}</p>
              <span class="source-badge">Source · {esc(row.get("source"))}</span>
            </div>
            """
        )
    show("".join(cards))

    cuts = []
    pace_rows = []
    for row in hooks[:4]:
        script = row.get("script_structure") or {}
        cut = script.get("cut_seconds")
        if isinstance(cut, (int, float)):
            cuts.append(float(cut))
            cut_label = f"{float(cut):.1f}s"
        else:
            cut_label = "Unpublished"
        pace_rows.append(
            f"""
            <div class="pace-row" style="padding:12px 0;border-top:1px solid #E2E2DC;">
              <div>
                <div class="kicker">{esc(script.get("audio") or "Audio not listed")}</div>
                <p class="meta-line">{esc(row.get("hook_text"))}</p>
              </div>
              <div class="serif" style="font-size:22px;">{esc(cut_label)}</div>
            </div>
            """
        )
    if cuts:
        headline = f"{sum(cuts) / len(cuts):.1f}s"
        caption = "Average cut frequency"
        why = "Cut speed is the region’s tolerance for silence. Match it, then hold one shot a beat longer so the film feels considered."
    else:
        headline = "—"
        caption = "Cut speed unpublished"
        why = "These clips did not publish a cut rate. Judge the opening line, not a pace number."
    source = hooks[0].get("source") or "STUDIO BASELINE"
    show(
        f"""
        <div class="card">
          <div class="card-top">
            <div>
              <div class="kicker">Audio &amp; pacing</div>
              <p class="pace-num">{headline}</p>
              <p class="note">{esc(caption)}</p>
            </div>
          </div>
          {"".join(pace_rows)}
          <p class="why">{esc(why)}</p>
          <span class="source-badge">Source · {esc(source)}</span>
        </div>
        """
    )


def render_proposal(text: str, source: str) -> None:
    blocks = []
    for title, body in split_proposal(text):
        body_html = rich(body)
        if title.strip().startswith("3."):
            body_html = f'<div class="pitch-line">{body_html}</div>'
        blocks.append(
            f"""
            <div class="card">
              <h3>{esc(title)}</h3>
              {body_html}
              <span class="source-badge">Source · {esc(source)}</span>
            </div>
            """
        )
    show("".join(blocks))


def render_strategy(region: dict, timeframe: str, visuals: list[dict], hooks: list[dict], domains: list[dict]) -> None:
    show(
        f"""
        <div class="section-head">
          <h2>Strategic assistant</h2>
          <p>A pitch for {esc(region["short"])}, grounded in the {esc(timeframe.lower())} cache on this desk.</p>
        </div>
        """
    )
    show(
        f'<p class="why" style="margin-bottom:0.7rem;">Grounded in {len(visuals)} formats, {len(hooks)} hooks, and {len(domains)} positions currently in view.</p>'
    )
    brief = st.text_area(
        "Client brief",
        height=150,
        placeholder="Varna dental clinic launching high-end veneers, needs brand redesign and ad campaign",
        key="client_brief",
    )
    if press("Generate Strategic Proposal", key="generate", primary=True, disabled=not brief.strip()):
        context = compose_context(region["label"], timeframe, visuals, hooks, domains)
        with st.spinner("Composing the pitch…"):
            result = propose(brief, context)
        st.session_state["proposal"] = {
            "region": region["id"],
            "brief": brief.strip(),
            "ok": result["ok"],
            "text": result.get("text") or "",
            "error": result.get("error") or "",
            "model": result.get("model") or "",
        }
        if result["ok"]:
            insert_proposal(region["id"], brief.strip(), result["text"])
    proposal = st.session_state.get("proposal")
    if proposal and proposal.get("region") == region["id"]:
        if proposal.get("ok") and proposal.get("text"):
            source = "DEEPSEEK"
            if proposal.get("model"):
                source = f"DEEPSEEK · {proposal['model']}"
            render_proposal(proposal["text"], source)
        elif proposal.get("error"):
            show(
                f"""
                <div class="card">
                  <h3>The strategist did not answer</h3>
                  <p class="why">{esc(proposal.get("error"))} The brief is still in the box. The regional cache was not changed.</p>
                </div>
                """
            )
    history = recent_proposals(region["id"], timeframe, limit=5)
    current_text = (proposal or {}).get("text") if proposal and proposal.get("region") == region["id"] else ""
    older = [row for row in history if row.get("generated_proposal") != current_text]
    if older:
        with st.expander("Previous proposals"):
            for row in older:
                show(
                    f"""
                    <div class="card">
                      <div class="kicker">{esc(format_stamp(row.get("timestamp")))}</div>
                      <p class="meta-line">{esc(row.get("client_brief"))}</p>
                    </div>
                    """
                )
                render_proposal(row.get("generated_proposal") or "", "DEEPSEEK")


def render_desk() -> None:
    render_masthead()
    region_id, timeframe = render_controls()
    region = region_by_id(region_id)
    visuals = fetch_visuals(region_id, timeframe)
    hooks = fetch_hooks(region_id, timeframe)
    domains = fetch_domains(region_id, timeframe)
    visual_tab, hook_tab, strategy_tab = st.tabs(
        ["Visual & Brand Radar", "Short-Form Hook Engine", "Strategic Assistant"]
    )
    with visual_tab:
        render_visuals(region, visuals, domains)
    with hook_tab:
        render_hooks(region, timeframe, hooks)
    with strategy_tab:
        render_strategy(region, timeframe, visuals, hooks, domains)
    show('<p class="footer">diArtis Studio · Varna · For pitch preparation</p>')


def main() -> None:
    st.set_page_config(
        page_title="diArtis Studio — Market Intelligence",
        page_icon="◆",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_css()
    try:
        init_db()
        seed_if_empty()
    except Exception as exc:
        show(
            f"""
            <div class="card">
              <h3>The local cache did not open</h3>
              <p class="why">{esc(scrub(str(exc))[:240])}</p>
            </div>
            """
        )
        return
    render_desk()


main()
