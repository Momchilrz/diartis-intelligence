"""Labeled war-room evidence for every geography and timeframe.

Rows are rehearsal intelligence. The card says Studio baseline. A live refresh
stores Serper and TikTok rows beside these and the desk prefers those.

Hours ago decide which pill can see the row:
  under 24 hours  -> 24 Hours, 7 Days, and 30 Days
  2 to 6 days     -> 7 Days and 30 Days
  10 to 25 days   -> 30 Days only
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import DB_PATH, REGION_IDS, SOURCE_BASELINE, TIMEFRAMES
from data.db import (
    connect,
    fetch_domains,
    fetch_hooks,
    fetch_radar,
    fetch_visuals,
    init_db,
    insert_domain,
    insert_hook,
    insert_radar,
    insert_visual,
    table_count,
)

_HEX = re.compile(r"^#[0-9A-F]{6}$")

HIGH = "HIGH CONVERSION SIGNAL — ROAS PROVEN"
HOLDING = "HOLDING — SPEND STILL ON"
SHORT = "SHORT RUN — NOT YET PROVEN"
TIRED = "FATIGUED — CREATIVE SWAP DUE"


def _hours_ago(hours: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(hours=hours)
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _ad(region, hours, brand, niche, ad_format, days, signal, colors, note):
    return {
        "region": region,
        "hours": hours,
        "brand_name": brand,
        "niche": niche,
        "ad_format": ad_format,
        "active_days": days,
        "signal": signal,
        "hex_codes": colors,
        "strategy_note": note,
        "insight": note,
    }


def _radar(region, hours, niche, pct, color_name, hx, note):
    return {
        "region": region,
        "hours": hours,
        "niche": niche,
        "saturation_pct": pct,
        "color_name": color_name,
        "dominant_hex": hx,
        "whitespace_note": note,
        "insight": note,
    }


def _hook(region, hours, text, archetype, views, pace, tier, friction, value, cta, insight):
    return {
        "region": region,
        "hours": hours,
        "hook_text": text,
        "archetype": archetype,
        "views_label": views,
        "pace_label": pace,
        "engagement_tier": tier,
        "insight": insight,
        "script_structure": {
            "hook": text,
            "friction": friction,
            "value": value,
            "cta": cta,
        },
    }


def _domain(
    region,
    hours,
    domain,
    keyword,
    position,
    change,
    movement,
    traffic,
    status,
    insight,
    share,
    where,
    question,
):
    return {
        "region": region,
        "hours": hours,
        "domain_name": domain,
        "target_keyword": keyword,
        "rank_position": position,
        "rank_change": change,
        "movement_label": movement,
        "monthly_traffic": traffic,
        "search_status": status,
        "insight": insight,
        "objection_share": share,
        "objection_where": where,
        "objection_text": question,
    }


ADS = [
    _ad(
        "varna_razgrad", 6,
        "Monblan Design (Varna)", "Interior studios",
        "Carousel / High-Contrast Typography", 38, HIGH,
        ["#4C5539", "#F8F8F5", "#D4A373", "#1A1A1A", "#E7E2D6"],
        "Uses minimalist editorial layouts to stand out against noisy discount banners.",
    ),
    _ad(
        "varna_razgrad", 18,
        "Meridian Dental (Razgrad)", "Medical and dental",
        "Static before-and-after", 22, HOLDING,
        ["#00A8FF", "#FFFFFF", "#E8F6FF", "#0B3A66", "#1A1A1A"],
        "Cold clinical blue with a whitened smile. The same frame as three other Razgrad clinics.",
    ),
    _ad(
        "varna_razgrad", 80,
        "Casa Nord (Varna)", "Apartment renovations",
        "Story sequence / material close-up", 17, HOLDING,
        ["#C4A574", "#F3EFE6", "#24352C", "#FFFFFF", "#8C947D"],
        "Brass and plaster stills aimed at sea-side apartment renovations.",
    ),
    _ad(
        "varna_razgrad", 400,
        "Razgrad Fix", "Home services",
        "Price-burst carousel", 9, TIRED,
        ["#FFD100", "#111111", "#E31C23", "#FFFFFF", "#2B2B2B"],
        "Yellow sticker bursts. High frequency, low brand recall outside the discount.",
    ),
    _ad(
        "bulgaria", 6,
        "Paper & Co (Sofia)", "Branding studios",
        "Editorial grid / serif headline", 44, HIGH,
        ["#1A1A1A", "#F4F4F1", "#9A3B2F", "#D8D4CC", "#4C5539"],
        "Black type on warm paper. The dried red is used once, on the project title.",
    ),
    _ad(
        "bulgaria", 18,
        "Northform (Sofia)", "Clinic performance",
        "Gradient square", 11, SHORT,
        ["#6C2BD9", "#FF4D8D", "#111111", "#FFFFFF", "#22C55E"],
        "Purple-to-pink gradient is the paid default for Sofia clinic offers this month.",
    ),
    _ad(
        "bulgaria", 100,
        "Gridline (Sofia)", "Web studios",
        "Founder portrait on grey seamless", 27, HOLDING,
        ["#E4E7DF", "#1A1A1A", "#FFFFFF", "#8A7968", "#4C5539"],
        "The portrait is holding. The grey seamless is the part that looks rented.",
    ),
    _ad(
        "bulgaria", 460,
        "Branch & Gold (Sofia)", "Finance and law",
        "Navy and gold lockup", 60, HIGH,
        ["#0B3A66", "#C5A46E", "#F5F7FA", "#1A1A1A", "#FFFFFF"],
        "Navy and gold still signals a branch. It is trusted, and it is interchangeable.",
    ),
    _ad(
        "greece_romania", 7,
        "Aegean Form (Thessaloniki)", "Hospitality",
        "Plaster still / single water color", 34, HIGH,
        ["#F6F1E8", "#1F4E5F", "#D08C60", "#E6E1D6", "#2C2C2C"],
        "One deep-water color on plaster. The terracotta neighbors are doing the sunset instead.",
    ),
    _ad(
        "greece_romania", 20,
        "Casa Atelier (Bucharest)", "Direct response",
        "Black, white, and a red price circle", 14, SHORT,
        ["#0E0E0E", "#F2F2F2", "#E10600", "#BFBFBF", "#1A1A1A"],
        "The fee sits in a siren-red circle. The contrast is working. The circle makes the fee feel cheap.",
    ),
    _ad(
        "greece_romania", 90,
        "Plaster Studio (Athens)", "Interior studios",
        "Lookbook beige carousel", 21, HOLDING,
        ["#E7E2DC", "#6E2E2A", "#CDB8A0", "#1A1A1A", "#F7F5F2"],
        "Beige lookbook frames. Half the premium Athens feed is now this costume.",
    ),
    _ad(
        "greece_romania", 420,
        "Nordclinic (Bucharest)", "Medical and dental",
        "Turquoise clinic template", 48, HIGH,
        ["#E5F4F3", "#0E7C86", "#FFFFFF", "#F2D6C9", "#163A3D"],
        "Turquoise and white has been live for 48 days. It converts, and it looks like every other clinic.",
    ),
    _ad(
        "balkans", 5,
        "Sava Atelier (Belgrade)", "Branding studios",
        "Olive editorial table", 44, HIGH,
        ["#F3F0E6", "#4C5539", "#C4A574", "#1A1A1A", "#E4E0D4"],
        "Olive and brass, now shared from Varna to Belgrade. The grid is the only ownable part.",
    ),
    _ad(
        "balkans", 16,
        "Adria House (Split)", "Hotels",
        "Stone lobby still", 55, HIGH,
        ["#D9D3C9", "#8A8175", "#F8F8F5", "#3F4A3C", "#A64B2A"],
        "Lobby stone has been on for 55 days. Guests cannot tell which hotel they are looking at.",
    ),
    _ad(
        "balkans", 120,
        "Skopje Form", "Restaurants",
        "Copper-on-night still", 15, HOLDING,
        ["#1C1A17", "#B87333", "#F4EFE6", "#8C8478", "#3E4A3A"],
        "Copper on near-black is the restaurant ad of the season across three capitals.",
    ),
    _ad(
        "balkans", 520,
        "Regional Sale Network", "Cross-border retail",
        "Primary-color sticker block", 9, TIRED,
        ["#FFD100", "#111111", "#FFFFFF", "#E31C23", "#0057B8"],
        "Primary-color sale blocks travel well and look identical once the city name is covered.",
    ),
    _ad(
        "world", 8,
        "Quiet Form", "Editorial web studios",
        "Gallery white / black wordmark", 38, HIGH,
        ["#F7F7F5", "#161616", "#E5E2DA", "#8C8C8C", "#4C5539"],
        "White space and a black wordmark. The margin rhythm is the only difference left.",
    ),
    _ad(
        "world", 18,
        "Margin & Co", "Luxury brand studios",
        "Near-black product film still", 64, HIGH,
        ["#0F1110", "#E7E8E4", "#9AA59A", "#FFFFFF", "#5C6654"],
        "Near-black product films still signal technology. The grey is anonymous.",
    ),
    _ad(
        "world", 96,
        "Atelier Index", "Beauty",
        "Cosmetic red wash", 12, SHORT,
        ["#F3E6E4", "#7A1E2C", "#1A1A1A", "#E7D3C4", "#FFFFFF"],
        "A dried red used as a background wash. It no longer points at one house.",
    ),
    _ad(
        "world", 480,
        "Rented Wall Co", "B2B services",
        "Talking head on an apartment wall", 21, HOLDING,
        ["#EFECE6", "#222222", "#C8B69A", "#F8F8F5", "#6E6A62"],
        "A talking head on a rented wall is the global B2B default. A locked-off table is the exit.",
    ),
]

RADAR = [
    _radar(
        "varna_razgrad", 8,
        "Medical and dental in Varna", 85, "Cold Medical Blue", "#00A8FF",
        "High visual whitespace for Deep Olive and Natural Earth Tones.",
    ),
    _radar(
        "varna_razgrad", 96,
        "Interior studios in Varna", 72, "Warm Beige", "#E7E2D6",
        "Whitespace left for deep olive type on warm off-white, with one brass accent.",
    ),
    _radar(
        "varna_razgrad", 440,
        "Home services in Razgrad", 91, "Sticker Yellow", "#FFD100",
        "Almost no quiet editorial ad is running. That gap is the pitch.",
    ),
    _radar(
        "bulgaria", 8,
        "Branding studios in Sofia", 78, "Gallery Black", "#1A1A1A",
        "Whitespace for a warm paper ground and one dried red. Not a gradient.",
    ),
    _radar(
        "bulgaria", 110,
        "Clinic performance in Sofia", 88, "Gradient Purple", "#6C2BD9",
        "Whitespace for a still life and charcoal type. The gradient is the crowded lane.",
    ),
    _radar(
        "bulgaria", 500,
        "Finance and law in Sofia", 81, "Navy Gold", "#0B3A66",
        "A consumer brand still has room on any ground that does not look like a bank branch.",
    ),
    _radar(
        "greece_romania", 6,
        "Hospitality from Thessaloniki to the islands", 83, "Terracotta", "#D08C60",
        "Whitespace is plaster white with one deep water color, and no sunset gradient.",
    ),
    _radar(
        "greece_romania", 100,
        "Direct response in Bucharest", 76, "Siren Red", "#E10600",
        "Whitespace is the fee set in the same type as the promise, with no circle.",
    ),
    _radar(
        "greece_romania", 460,
        "Clinics in Bucharest and Athens", 89, "Clinic Turquoise", "#0E7C86",
        "Whitespace is a warm grey room and charcoal type.",
    ),
    _radar(
        "balkans", 6,
        "Studios across five capitals", 80, "Shared Olive", "#4C5539",
        "The olive is no longer whitespace. A stricter grid is the open move.",
    ),
    _radar(
        "balkans", 120,
        "Hotels along the Adriatic and inland", 77, "Lobby Stone", "#D9D3C9",
        "Whitespace is one named material a guest can point at, held for three seconds.",
    ),
    _radar(
        "balkans", 500,
        "Restaurant ads in Belgrade, Sofia, and Athens", 74, "Copper Night", "#B87333",
        "Whitespace is daylight and a white cloth. Night copper is the shared room.",
    ),
    _radar(
        "world", 8,
        "Global studio sites", 84, "Gallery White", "#F7F7F5",
        "Whitespace is the margin rhythm, and the one color you are willing to repeat for a year.",
    ),
    _radar(
        "world", 90,
        "Beauty campaigns", 79, "Cosmetic Red", "#7A1E2C",
        "Use the red as a material, a lipstick or a glaze, not as a background wash.",
    ),
    _radar(
        "world", 520,
        "Technology product films", 73, "Near Black", "#0F1110",
        "Borrow the discipline. Replace the anonymous grey with a color that has a place.",
    ),
]

HOOKS = [
    _hook(
        "varna_razgrad", 5,
        "3 things most clinics in Varna won't tell you about veneers...",
        "Negative Friction / Curiosity Gap",
        "145K views", "Fast cut pace (1.1s)", "High velocity",
        "Most people overpay for low-quality composite bonding.",
        "Show a 3-second close-up of natural translucency veneers.",
        "Book a 15-min digital visual audit.",
        "The numbered list holds the viewer. The city name keeps it from sounding imported.",
    ),
    _hook(
        "varna_razgrad", 16,
        "The Varna apartment everyone saves is not the one with the gold handles.",
        "Pattern Interrupt",
        "86K views", "Medium cut pace (1.8s)", "High velocity",
        "Showroom gold reads expensive in the feed and cheap in the room.",
        "One plaster wall, one oak edge, one named light.",
        "Send the floor plan for a material shortlist.",
        "The refusal of gold is the first frame. The next frame has to be the material, not another mood shot.",
    ),
    _hook(
        "varna_razgrad", 110,
        "Razgrad patients scroll past the blue smile in under a second.",
        "Negative Friction",
        "41K views", "Fast cut pace (0.9s)", "Emerging",
        "Every clinic ad in the city is the same chair and the same blue.",
        "Open on the fee, then the ceramic, then the room.",
        "Put the real fee on the first screen of the site.",
        "Half a second is the edit brief. If the first frame could be any clinic, it is already gone.",
    ),
    _hook(
        "varna_razgrad", 500,
        "We filmed the veneer in north window light. No whitening filter.",
        "Behind-The-Scenes",
        "19K views", "Slow hold (2.6s)", "Quiet",
        "Speed ramps make porcelain look plastic.",
        "Hold the real light until the material reads as ceramic.",
        "Use the same still as the website hero.",
        "Slow light is the contrast against the fast blue ads. Let the white look like porcelain.",
    ),
    _hook(
        "bulgaria", 7,
        "Sofia clinics are buying the same purple ad. Here is the frame they are not buying.",
        "Pattern Interrupt",
        "210K views", "Fast cut pace (1.0s)", "Breakout",
        "The gradient square is the paid default, so it no longer stops the scroll.",
        "A still life on warm paper, one object, charcoal type.",
        "Replace the hero before buying more traffic.",
        "Name the crowded color, then show the frame that is absent from the auction.",
    ),
    _hook(
        "bulgaria", 18,
        "If the homepage type is a default sans, the luxury claim is already false.",
        "Negative Friction",
        "96K views", "Medium cut pace (1.6s)", "High velocity",
        "A premium claim set in a default sans is the tell.",
        "One serif, one size scale, wider margins.",
        "Reset the hero before the next media flight.",
        "The type is the evidence. Put the current site and the reset side by side.",
    ),
    _hook(
        "bulgaria", 120,
        "Three applications. Then the symbol. Not the other way around.",
        "Direct Statement",
        "54K views", "Medium cut pace (1.4s)", "Emerging",
        "New Sofia identities are still launching as a symbol, a gradient, and a slogan.",
        "Lead with type, margin, and one repeated color.",
        "Show the menu, the card, and the film before the mark.",
        "The order is the strategy. The symbol arrives after the system is visible.",
    ),
    _hook(
        "bulgaria", 480,
        "We turned the playlist off and filmed the paper.",
        "Behind-The-Scenes",
        "28K views", "Slow hold (2.8s)", "Quiet",
        "Studio films in Sofia have started to share the same three tracks.",
        "Paper, knife, and the sound of the room.",
        "End on the finished piece, not on the team waving.",
        "Silence is a positioning choice. It makes a process film feel considered.",
    ),
    _hook(
        "greece_romania", 6,
        "Athens does not need another beige room. Watch the plaster instead.",
        "Pattern Interrupt",
        "132K views", "Medium cut pace (1.4s)", "High velocity",
        "Beige lookbooks have made half the premium market indistinguishable.",
        "Plaster white and one deep water color, then stop.",
        "Apply it to the menu, the room, and the film.",
        "Refuse the costume palette in the first line. The next frame has to prove the alternative.",
    ),
    _hook(
        "greece_romania", 18,
        "Your Bucharest price is in a red circle. That is why it feels cheap.",
        "Negative Friction",
        "118K views", "Fast cut pace (0.8s)", "High velocity",
        "Performance ads circle the fee as if it were a siren.",
        "Set the price in the same type as the promise, with no badge.",
        "Show the fee once, after the proof.",
        "Screenshot their ad and set the fee properly beside it. The graphic habit is the brand problem.",
    ),
    _hook(
        "greece_romania", 100,
        "We filmed the plaster, not the skyline.",
        "Behind-The-Scenes",
        "64K views", "Slow hold (2.4s)", "High velocity",
        "Every hospitality film opens on the same drone shot of the coast.",
        "A material, held, tells a guest more than a coastline.",
        "Open the campaign on the surface, then the room.",
        "Drone shots are the shared footage. A surface is ownable.",
    ),
    _hook(
        "greece_romania", 450,
        "Bucharest scrolls past stock smiles in half a second.",
        "Negative Friction",
        "37K views", "Fast cut pace (1.2s)", "Quiet",
        "Clinic ads are still buying the same smile from the same library.",
        "Film one real patient moment, or none.",
        "Put the real still on the first screen of the site.",
        "If the first frame could be any clinic, the half-second is already spent.",
    ),
    _hook(
        "balkans", 5,
        "If this palette works in five capitals, it is not a brand yet.",
        "Pattern Interrupt",
        "173K views", "Medium cut pace (1.5s)", "Breakout",
        "Olive, brass, and a serif are now a regional costume.",
        "Keep the colors only if the grid and the sentence are stricter than the neighbors.",
        "Name the one rule the other capitals are breaking.",
        "This stops a moodboard from being mistaken for a position.",
    ),
    _hook(
        "balkans", 16,
        "Stop opening the hotel film on a drone.",
        "Pattern Interrupt",
        "88K views", "Fast cut pace (1.0s)", "High velocity",
        "Coast, mountains, and a sunset read as a tourism board, not a house.",
        "Promise one guest, one room, one meal.",
        "Cut the aerials before the meeting.",
        "Replacing the drone shot is the easiest visible difference in the deck.",
    ),
    _hook(
        "balkans", 130,
        "The chef plated it. We did not grade it.",
        "Behind-The-Scenes",
        "59K views", "Slow hold (2.2s)", "High velocity",
        "Food films in the region are graded until every plate matches.",
        "Leave the color of the room. Correct nothing the chef did not cook.",
        "Show the grade turned off, side by side.",
        "The line defends a quieter grade. Clients understand it when they see the filter they almost bought.",
    ),
    _hook(
        "balkans", 540,
        "Your hotel film looks like the hotel across the border.",
        "Negative Friction",
        "24K views", "Medium cut pace (1.9s)", "Quiet",
        "The same lobby stone, the same copper night, the same piano.",
        "Photograph the one material that exists only in that building.",
        "Open on that material for three seconds before the logo.",
        "Treat the neighboring hotel as the reference, not a global campaign.",
    ),
    _hook(
        "world", 8,
        "Do not show the logo in the first second.",
        "Pattern Interrupt",
        "310K views", "Fast cut pace (1.2s)", "Breakout",
        "Opening on the symbol trains people to skip it.",
        "Open on the problem the brand exists to fix. Land the mark after the proof.",
        "Time the logo to the fourth second and watch the hold.",
        "You can demonstrate this in the room by covering the logo with a hand.",
    ),
    _hook(
        "world", 20,
        "Pretty is now the easy part. Name the thing you refuse.",
        "Pattern Interrupt",
        "188K views", "Slow hold (2.0s)", "Breakout",
        "Tasteful frames are abundant. A point of view is not.",
        "Decide the one thing the work refuses, and show that refusal.",
        "Put the refusal on the first board, before the mockups.",
        "Move the meeting from beauty to the decision the beauty is hiding.",
    ),
    _hook(
        "world", 100,
        "This is the color we refused, and the competitor who owns it.",
        "Behind-The-Scenes",
        "72K views", "Slow hold (2.5s)", "Emerging",
        "Palettes are being presented as preferences instead of decisions.",
        "Show the rejected swatch and the competitor it belongs to.",
        "Leave the refused color in the appendix, labeled.",
        "A rejected color is more persuasive than a chosen one, because it shows the studio can say no.",
    ),
    _hook(
        "world", 500,
        "The case study is four screens too long.",
        "Negative Friction",
        "33K views", "Medium cut pace (1.5s)", "Quiet",
        "Process sections repeat the same three steps in new nouns.",
        "Keep the constraint, the move, and the result.",
        "Rewrite one case study to a single screen before the pitch.",
        "Length is being mistaken for rigor. A shorter study leaves room for the recommendation.",
    ),
]

DOMAINS = [
    _domain(
        "varna_razgrad", 7,
        "monblan-design.com", "интериорен дизайн варна",
        6, 3, "+3 ranks in the last 7 days", "~4.2k",
        "🔥 +45% search spike in the Varna region",
        "Competitor increased landing page content targeting high-end apartment renovations.",
        "65%", "Varna agency and clinic ads", "Do you offer custom payment plans?",
    ),
    _domain(
        "varna_razgrad", 18,
        "meridian-dental.bg", "зъбни импланти разград",
        3, 0, "Holding rank in the last 7 days", "~2.8k",
        "🔥 +12% search spike in Razgrad",
        "Position 3 still leads with the chair photo and a phone number.",
        "58%", "Razgrad implant ads", "Is the implant price the full price, or are the scans extra?",
    ),
    _domain(
        "varna_razgrad", 120,
        "atelier-varna.bg", "интериорен дизайн варна",
        4, 1, "+1 rank in the last 7 days", "~3.1k",
        "🔥 +18% search spike in the Varna region",
        "The gallery grew by six project pages aimed at apartment renovations.",
        "47%", "Varna interior comment threads", "Can you work with the contractor we already hired?",
    ),
    _domain(
        "varna_razgrad", 520,
        "diartis.studio", "дигитален маркетинг варна",
        8, 2, "+2 ranks in the last 30 days", "~1.6k",
        "🔥 +9% search spike in the Varna region",
        "Still the bottom of the first screen. The page has to look quieter than the agencies above it.",
        "39%", "Varna marketing ads", "Do you only work with Varna businesses?",
    ),
    _domain(
        "bulgaria", 6,
        "paper-and-co.bg", "брандинг агенция софия",
        2, 0, "Holding rank in the last 7 days", "~9.4k",
        "🔥 +8% search spike in Sofia",
        "Position 2 already takes the click. The deck should critique their first screen.",
        "44%", "Sofia branding comment threads", "Can you show work for a clinic, not another cafe?",
    ),
    _domain(
        "bulgaria", 16,
        "northform.bg", "реклама за клиники",
        5, 4, "+4 ranks in the last 7 days", "~6.1k",
        "🔥 +33% search spike in Sofia",
        "The clinic query is moving. The winning page looks like a practice, not an agency menu.",
        "71%", "Sofia clinic ads", "Will the ads look like every other dental offer?",
    ),
    _domain(
        "bulgaria", 110,
        "gridline.bg", "уеб дизайн софия",
        12, -2, "−2 ranks in the last 7 days", "~2.4k",
        "Flat search volume in Sofia",
        "Position 12 is off the first screen. Do not lead the meeting with search.",
        "36%", "Sofia web-design threads", "How fast can a new homepage go live?",
    ),
    _domain(
        "bulgaria", 480,
        "diartis.studio", "creative agency sofia",
        8, 1, "+1 rank in the last 30 days", "~3.3k",
        "🔥 +11% search spike in Sofia",
        "Position 8 is the bottom of the first screen. The page above the fold has to be quieter than positions 1 to 3.",
        "29%", "Sofia agency ads", "Do you fly to Sofia for the kickoff?",
    ),
    _domain(
        "greece_romania", 6,
        "aegean-form.gr", "digital agency thessaloniki",
        5, 2, "+2 ranks in the last 7 days", "~5.6k",
        "🔥 +22% search spike in Thessaloniki",
        "Position 5 leaves a gap above. A plaster-white page with one project looks more specific than a full-service grid.",
        "52%", "Thessaloniki hospitality ads", "Can you shoot the room, or only the website?",
    ),
    _domain(
        "greece_romania", 18,
        "casa-atelier.ro", "agentie branding bucuresti",
        3, 0, "Holding rank in the last 7 days", "~7.8k",
        "🔥 +6% search spike in Bucharest",
        "Position 3 is taken. Beat them on the first screen of the work, not on a longer service list.",
        "61%", "Bucharest branding ads", "Is the fee the red number, or the real project price?",
    ),
    _domain(
        "greece_romania", 100,
        "plasterstudio.gr", "interior studio athens",
        7, 1, "+1 rank in the last 7 days", "~3.4k",
        "🔥 +15% search spike in Athens",
        "The hotels above are sharing one beige lookbook. A material-led page is the opening.",
        "43%", "Athens interior threads", "Do you design the room, or only the pictures of it?",
    ),
    _domain(
        "greece_romania", 460,
        "nordclinic.ro", "fatete dentare bucuresti",
        4, -2, "−2 ranks in the last 30 days", "~8.9k",
        "🔥 +19% search spike in Bucharest",
        "Position 4 on a treatment query. The click is going to turquoise clinic templates.",
        "68%", "Bucharest veneer ads", "How many visits before I see the result?",
    ),
    _domain(
        "balkans", 5,
        "sava-atelier.rs", "branding agency belgrade",
        6, 2, "+2 ranks in the last 7 days", "~4.7k",
        "🔥 +27% search spike in Belgrade",
        "Position 6 is reachable. The olive palette is already shared, so the difference to show is the grid.",
        "49%", "Belgrade studio threads", "Will this look like every other olive brand in the region?",
    ),
    _domain(
        "balkans", 16,
        "adria-house.hr", "boutique hotel design",
        4, 0, "Holding rank in the last 7 days", "~6.2k",
        "🔥 +14% search spike across Adriatic hotel queries",
        "Position 4 is the competitive set for a hotel identity. Their page is the one to be quieter than.",
        "57%", "hotel film comment threads", "Can a guest tell this hotel from the one across the bay?",
    ),
    _domain(
        "balkans", 140,
        "diartis.studio", "balkan branding studio",
        11, 3, "+3 ranks in the last 30 days", "~1.9k",
        "🔥 +18% search spike on Balkan studio queries",
        "Position 11 is off the first screen. Lead the meeting with the work.",
        "34%", "regional studio threads", "Do you have a project in our city, or only in Varna?",
    ),
    _domain(
        "balkans", 560,
        "skopje-form.mk", "design studio skopje",
        8, -1, "−1 rank in the last 30 days", "~2.1k",
        "🔥 +4% search spike in Skopje",
        "Position 8 still sits on the first screen. One named material distinguishes the work faster than a new symbol.",
        "41%", "Skopje studio threads", "Can you present in person, or only on a call?",
    ),
    _domain(
        "world", 8,
        "quietform.co", "editorial website design",
        4, 0, "Holding rank in the last 7 days", "~18k",
        "🔥 +11% search spike on editorial web queries",
        "Position 4 is the reference for editorial web. Study the margins, then make one decision they will not make.",
        "38%", "editorial web threads", "How is this different from a white template with a serif?",
    ),
    _domain(
        "world", 20,
        "atelier-index.com", "brand identity studio",
        9, 5, "+5 ranks in the last 7 days", "~11k",
        "🔥 +38% search spike on identity-studio queries",
        "Position 9 after a sharp move up. The page is being rewarded. Change the color they are using as a wash.",
        "46%", "identity-studio threads", "Can you show the colors you refused, not only the ones you kept?",
    ),
    _domain(
        "world", 110,
        "marginandco.com", "luxury brand studio",
        6, -1, "−1 rank in the last 7 days", "~14k",
        "🔥 +7% search spike on luxury studio queries",
        "Position 6 is the middle of the first screen. Luxury queries punish sameness.",
        "53%", "luxury studio threads", "What do you refuse that the other luxury studios still offer?",
    ),
    _domain(
        "world", 500,
        "diartis.studio", "boutique branding studio",
        14, 2, "+2 ranks in the last 30 days", "~2.2k",
        "🔥 +5% search spike on boutique studio queries",
        "Position 14 is not the pitch. Do not pretend search is how this client will be won.",
        "27%", "boutique studio threads", "Are you a local studio that travels, or a remote team?",
    ),
]


def _check() -> None:
    buckets = {
        "ads": ADS,
        "radar": RADAR,
        "hooks": HOOKS,
        "domains": DOMAINS,
    }
    for name, bucket in buckets.items():
        unknown = {row["region"] for row in bucket} - REGION_IDS
        if unknown:
            raise ValueError(f"Unknown regions in {name}: {unknown}")
        counts: dict[str, int] = {}
        for row in bucket:
            counts[row["region"]] = counts.get(row["region"], 0) + 1
        missing = REGION_IDS - set(counts)
        if missing or any(counts[region] < 3 for region in counts):
            raise ValueError(f"{name} must cover every region: {counts}")
    for row in ADS:
        colors = row["hex_codes"]
        if not 3 <= len(colors) <= 5 or any(_HEX.match(color) is None for color in colors):
            raise ValueError(f"Palette must be three to five HEX colors: {row['brand_name']}")
        if not row["brand_name"] or not row["strategy_note"] or not row["signal"]:
            raise ValueError(f"Ad card is missing a label: {row['brand_name']}")
    for row in RADAR:
        if _HEX.match(row["dominant_hex"]) is None:
            raise ValueError(f"Radar HEX is invalid: {row['niche']}")
        if not 1 <= int(row["saturation_pct"]) <= 100:
            raise ValueError(f"Saturation out of range: {row['niche']}")
    for row in HOOKS:
        script = row["script_structure"]
        if not all(script.get(key) for key in ("hook", "friction", "value", "cta")):
            raise ValueError(f"Hook is missing a beat: {row['hook_text']}")
        if "views" not in row["views_label"].lower() or not row["pace_label"]:
            raise ValueError(f"Hook is missing a performance label: {row['hook_text']}")
    for row in DOMAINS:
        if int(row["rank_position"]) < 1:
            raise ValueError(f"Rank must be labeled above zero: {row['domain_name']}")
        movement = row["movement_label"].strip()
        if len(movement) < 8 or movement.isdigit():
            raise ValueError(f"Movement must be a phrase: {row['domain_name']}")
        if not row["monthly_traffic"].startswith("~"):
            raise ValueError(f"Traffic must be a volume label: {row['domain_name']}")
        if not row["objection_share"].endswith("%") or not row["objection_text"]:
            raise ValueError(f"Objection must be labeled: {row['domain_name']}")


def _insert_all(conn) -> None:
    for row in ADS:
        insert_visual(
            {
                "region": row["region"],
                "hex_codes": row["hex_codes"],
                "ad_format": row["ad_format"],
                "active_days": row["active_days"],
                "screenshot_url": "",
                "timestamp": _hours_ago(row["hours"]),
                "insight": row["insight"],
                "source": SOURCE_BASELINE,
                "brand_name": row["brand_name"],
                "signal": row["signal"],
                "strategy_note": row["strategy_note"],
                "niche": row["niche"],
            },
            conn,
        )
    for row in RADAR:
        insert_radar(
            {
                "region": row["region"],
                "niche": row["niche"],
                "saturation_pct": row["saturation_pct"],
                "color_name": row["color_name"],
                "dominant_hex": row["dominant_hex"],
                "whitespace_note": row["whitespace_note"],
                "timestamp": _hours_ago(row["hours"]),
                "insight": row["insight"],
                "source": SOURCE_BASELINE,
            },
            conn,
        )
    for row in HOOKS:
        insert_hook(
            {
                "region": row["region"],
                "hook_text": row["hook_text"],
                "archetype": row["archetype"],
                "script_structure": row["script_structure"],
                "engagement_tier": row["engagement_tier"],
                "timestamp": _hours_ago(row["hours"]),
                "insight": row["insight"],
                "source": SOURCE_BASELINE,
                "views_label": row["views_label"],
                "pace_label": row["pace_label"],
            },
            conn,
        )
    for row in DOMAINS:
        insert_domain(
            {
                "region": row["region"],
                "domain_name": row["domain_name"],
                "target_keyword": row["target_keyword"],
                "rank_position": row["rank_position"],
                "rank_change": row["rank_change"],
                "timestamp": _hours_ago(row["hours"]),
                "insight": row["insight"],
                "source": SOURCE_BASELINE,
                "monthly_traffic": row["monthly_traffic"],
                "search_status": row["search_status"],
                "movement_label": row["movement_label"],
                "objection_share": row["objection_share"],
                "objection_where": row["objection_where"],
                "objection_text": row["objection_text"],
            },
            conn,
        )


def _wipe_files() -> None:
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(DB_PATH) + suffix)
        if path.exists():
            path.unlink()


def seed_if_empty() -> bool:
    _check()
    init_db()
    if table_count("visual_trends"):
        return False
    with connect() as conn:
        _insert_all(conn)
    return True


def reseed() -> None:
    """Drop the local cache and write a full labeled set for every region."""
    _check()
    _wipe_files()
    init_db()
    with connect() as conn:
        _insert_all(conn)
    gaps = []
    for region in sorted(REGION_IDS):
        windows = {}
        for timeframe in ("24 Hours", "7 Days", "30 Days"):
            counts = (
                len(fetch_visuals(region, timeframe)),
                len(fetch_radar(region, timeframe)),
                len(fetch_hooks(region, timeframe)),
                len(fetch_domains(region, timeframe)),
            )
            windows[timeframe] = counts
            if any(count < 1 for count in counts):
                gaps.append(f"{region} / {timeframe}: {counts}")
        ads = [windows[name][0] for name in ("24 Hours", "7 Days", "30 Days")]
        if not ads[0] < ads[1] < ads[2]:
            gaps.append(f"{region} ad windows did not widen: {windows}")
    if gaps:
        raise RuntimeError("Timeframe windows did not separate:\n" + "\n".join(gaps))


if __name__ == "__main__":
    reseed()
    print("reseeded intel_store.db")
    for region in ("varna_razgrad", "bulgaria", "greece_romania", "balkans", "world"):
        for timeframe in TIMEFRAMES:
            ads = fetch_visuals(region, timeframe)
            hooks = fetch_hooks(region, timeframe)
            domains = fetch_domains(region, timeframe)
            radar = fetch_radar(region, timeframe)
            print(
                f"{region:16} {timeframe:10} "
                f"ads={len(ads)} radar={len(radar)} hooks={len(hooks)} search={len(domains)}"
            )
