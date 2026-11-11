"""Baseline regional evidence so the desk is populated before any live call.

Every row is rehearsal material. The source badge says so. A live refresh
stores Serper and TikTok rows beside it and the desk prefers those.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from config import REGION_IDS, SOURCE_BASELINE
from data.db import init_db, insert_domain, insert_hook, insert_visual, table_count, connect

_HEX = re.compile(r"^#[0-9A-F]{6}$")


def _hours_ago(hours: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(hours=hours)
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _visual(region, hours, colors, ad_format, active_days, insight):
    return {
        "region": region,
        "hours": hours,
        "hex_codes": colors,
        "ad_format": ad_format,
        "active_days": active_days,
        "insight": insight,
    }


def _hook(region, hours, text, archetype, tier, audio, cut, friction, value, cta, insight):
    return {
        "region": region,
        "hours": hours,
        "hook_text": text,
        "archetype": archetype,
        "engagement_tier": tier,
        "insight": insight,
        "script_structure": {
            "hook": text,
            "friction": friction,
            "value": value,
            "cta": cta,
            "audio": audio,
            "cut_seconds": cut,
        },
    }


def _domain(region, hours, domain, keyword, position, change, insight):
    return {
        "region": region,
        "hours": hours,
        "domain_name": domain,
        "target_keyword": keyword,
        "rank_position": position,
        "rank_change": change,
        "insight": insight,
    }


VISUALS = [
    _visual("varna_razgrad", 8, ["#F3EFE6", "#24352C", "#C6A15B", "#E7E2D6", "#8C947D"], "Minimalist clinical still", 41, "Long-running clinic ads are warm paper plus one brass note. Leave the forest-green field alone; it is already the local default. Use the brass once, on the type."),
    _visual("varna_razgrad", 20, ["#F7F4EF", "#A33B24", "#1A1A1A", "#D9C7B0", "#FFFFFF"], "Face-led vertical crop", 19, "Vertical face crops are the local service default. Keep the face if you must, and set the caption in serif on warm paper so it reads as a fee, not a discount."),
    _visual("varna_razgrad", 96, ["#111111", "#F5C518", "#FFFFFF", "#C8102E", "#2B2B2B"], "Price-sticker carousel", 11, "Black and yellow price stickers still cover Razgrad home services. The open space is the reverse: uncoated white, one olive line, no burst."),
    _visual("varna_razgrad", 420, ["#E4E7DF", "#4C5539", "#F8F8F5", "#8A7968", "#1A1A1A"], "Founder in a real room", 52, "Founder portraits are holding for professional services, and the grey seamless is the tired version. Shoot the real room and crop tighter than a headshot template."),
    _visual("bulgaria", 8, ["#F4F4F1", "#1A1A1A", "#9A3B2F", "#D8D4CC", "#4C5539"], "Gallery grid", 33, "Sofia studio sites have converged on black-and-white grids. The whitespace is a warm paper ground and one dried red, used only for the title of the work."),
    _visual("bulgaria", 20, ["#EFE6D6", "#1E2A24", "#C45C26", "#F8F8F5", "#8C8478"], "Flat culture poster", 28, "Poster-like culture ads are holding attention with one crop and a flat ground. Borrow the crop. Leave the event-poster type."),
    _visual("bulgaria", 96, ["#6C2BD9", "#111111", "#FFFFFF", "#FF4D8D", "#22C55E"], "Gradient performance ad", 14, "Purple-to-pink performance creatives are the paid default. Refuse the gradient. A still life looks deliberate beside it."),
    _visual("bulgaria", 420, ["#0B3A66", "#F5F7FA", "#C5A46E", "#1A1A1A", "#FFFFFF"], "Navy and gold corporate", 60, "Navy and gold still signal trust for finance and law. For a premium consumer brand it reads as a branch. Keep the metal, change the ground."),
    _visual("greece_romania", 8, ["#F6F1E8", "#1F4E5F", "#D08C60", "#E6E1D6", "#2C2C2C"], "Plaster and deep water", 37, "Terracotta hospitality ads are crowded from Thessaloniki to the islands. The open move is plaster white with one deep water color, and no sunset gradient."),
    _visual("greece_romania", 20, ["#E7E2DC", "#6E2E2A", "#CDB8A0", "#1A1A1A", "#F7F5F2"], "Lookbook beige", 22, "Lookbook beige is the luxury costume of the season. Use it only when the product is actually stone, skin, or cloth."),
    _visual("greece_romania", 96, ["#0E0E0E", "#F2F2F2", "#E10600", "#BFBFBF", "#1A1A1A"], "Bucharest contrast ad", 16, "Bucharest direct-response is black, white, and a siren red. Keep the contrast. Drop the red circle around the price."),
    _visual("greece_romania", 420, ["#E5F4F3", "#0E7C86", "#FFFFFF", "#F2D6C9", "#163A3D"], "Clinic turquoise", 48, "Turquoise and white is the clinic uniform from Bucharest to Athens. A warm grey room and charcoal type is the visible gap."),
    _visual("balkans", 8, ["#F3F0E6", "#4C5539", "#C4A574", "#1A1A1A", "#E4E0D4"], "Shared olive table", 44, "Olive and brass now show up from Varna to Belgrade. The colors are no longer distinctive. A stricter grid is what makes them yours."),
    _visual("balkans", 20, ["#D9D3C9", "#8A8175", "#F8F8F5", "#3F4A3C", "#A64B2A"], "Stone hotel lobby", 55, "Lobby stone is the hospitality default. Photograph a material a guest can name: one stone, one metal, one plant."),
    _visual("balkans", 96, ["#1C1A17", "#B87333", "#F4EFE6", "#8C8478", "#3E4A3A"], "Copper on night", 15, "Copper on near-black is the restaurant ad of the season, and it all looks like the same room. Daylight and a white cloth is the contrast."),
    _visual("balkans", 420, ["#FFD100", "#111111", "#FFFFFF", "#E31C23", "#0057B8"], "Cross-border sale sticker", 9, "Primary-color sale blocks travel well and look interchangeable. A regional brand should still be recognizable with the stickers removed."),
    _visual("world", 8, ["#F7F7F5", "#161616", "#E5E2DA", "#8C8C8C", "#4C5539"], "Gallery white", 38, "Global studio sites have converged on white space and a black wordmark. The difference is the margin rhythm, and the one color you are willing to repeat for a year."),
    _visual("world", 20, ["#EFECE6", "#222222", "#C8B69A", "#F8F8F5", "#6E6A62"], "Rented-wall confessional", 21, "A talking head on a rented apartment wall is the global B2B default. A real table and a locked-off camera is enough to step out of it."),
    _visual("world", 96, ["#F3E6E4", "#7A1E2C", "#1A1A1A", "#E7D3C4", "#FFFFFF"], "Cosmetic red", 12, "A dried cosmetic red is everywhere in beauty. Use it as a material — a lipstick, a glaze — not as a background wash."),
    _visual("world", 420, ["#0F1110", "#E7E8E4", "#9AA59A", "#FFFFFF", "#5C6654"], "Near-black product film", 64, "Near-black product films still signal technology. Borrow the discipline, and replace the anonymous grey with a color that has a place."),
]

HOOKS = [
    _hook("varna_razgrad", 8, "Your clinic photos look expensive. The booking page does not.", "Negative Friction", "High velocity", "Dry voice, no music bed", 1.6, "The page asks for a phone number before it says what the visit costs.", "Show the room, the type, and the fee on the first screen.", "Book a twenty-minute read of the current page.", "The insult lands before the logo. Open the audit on the page itself, not a montage of the treatment room."),
    _hook("varna_razgrad", 20, "Stop opening with the treatment room.", "Pattern Interrupt", "Emerging", "Room tone under a close voice", 1.1, "Every clinic in the feed already shows the chair.", "Open on the patient's question, then the result, then the room.", "Keep this order for the next treatment launch.", "A pattern interrupt only works if the next frame is a different idea. Cut to a typeset fee, not another chair."),
    _hook("varna_razgrad", 96, "We shot the veneers in north window light. That is the whole ad.", "Behind-The-Scenes", "High velocity", "Original sound, camera shutter", 2.4, "Speed ramps and whitening filters make porcelain look plastic.", "Hold the real light long enough that the material reads as ceramic.", "Use the same light on the website hero.", "Slow light is the luxury signal in a feed of speed ramps. Let the white look like porcelain, not a filter."),
    _hook("varna_razgrad", 420, "Razgrad patients can tell a template in under a second.", "Negative Friction", "Quiet", "Voice only, hard stop", 1.8, "A global dental template with the city name swapped in still looks imported.", "One local proof, set in the studio's type, does more than a stock smile.", "Name the city only when the next frame proves it.", "The city keeps the line from sounding like a global ad. Follow it with one local proof, or it is just a slogan."),
    _hook("bulgaria", 8, "Sofia has enough logos. It does not have enough restraint.", "Pattern Interrupt", "High velocity", "Dry voice over room tone", 1.3, "New identities are still launching as a symbol, a gradient, and a slogan.", "Lead with the system: type, margin, and one repeated color.", "Show three applications before the symbol.", "The line gives you permission to present the grid before the logo. Use it."),
    _hook("bulgaria", 20, "If the ad needs five stickers, the offer is not ready.", "Negative Friction", "Emerging", "Voice only", 0.9, "Price bursts are covering a sentence that should have been clear.", "Rewrite the offer until it can stand in one line of type.", "Remove every sticker and read the line aloud.", "This is a writing test disguised as an ad note. Put the cleaned line on the first board."),
    _hook("bulgaria", 96, "A day in the studio, with the playlist turned off.", "Behind-The-Scenes", "Quiet", "No music, practical sounds only", 2.8, "Studio films have started to sound like the same three tracks.", "The work is more convincing with paper, knife, and silence.", "End on the finished piece, not on the team waving.", "Silence is a positioning choice. It makes a process film feel considered instead of cheerful."),
    _hook("bulgaria", 420, "The homepage says premium. The type says template.", "Negative Friction", "High velocity", "Close voice, no bed", 1.4, "A luxury claim set in a default sans with tight tracking is the tell.", "Reset the page in one serif, one size scale, and wider margins.", "Replace the hero before buying more traffic.", "Use this when the client wants ads and the page cannot hold them. The type is the evidence."),
    _hook("greece_romania", 8, "Athens does not need another beige brand.", "Pattern Interrupt", "High velocity", "Dry voice", 1.5, "Beige lookbooks have made half the premium market indistinguishable.", "Choose plaster white and one deep water color, then stop.", "Apply it to the menu, the room, and the film.", "Say the city, then refuse the costume palette. The next frame has to prove the alternative."),
    _hook("greece_romania", 20, "Your price is in a red circle. That is why it feels cheap.", "Negative Friction", "Emerging", "Hard-cut voice", 0.8, "Bucharest performance ads circle the fee as if it were a siren.", "Set the price in the same type as the promise, with no badge.", "Show the fee once, after the proof.", "The graphic habit is the brand problem. Screenshot their ad and set the fee properly beside it."),
    _hook("greece_romania", 96, "We filmed the plaster, not the skyline.", "Behind-The-Scenes", "High velocity", "Location sound, no score", 2.6, "Every hospitality film opens on the same drone shot of the coast.", "A material, held, tells a guest more than a coastline.", "Open the campaign on the surface, then the room.", "Drone shots are the shared footage of the region. A surface is ownable."),
    _hook("greece_romania", 420, "Bucharest scrolls past stock smiles in half a second.", "Negative Friction", "Quiet", "Voice only", 1.2, "Clinic ads are still buying the same smile from the same library.", "Film one real patient moment, or none. Do not illustrate dentistry.", "Put the real still on the first screen of the site too.", "Half a second is the brief for the edit. If the first frame could be any clinic, it is already gone."),
    _hook("balkans", 8, "If the palette works in five capitals, it is not a brand yet.", "Pattern Interrupt", "High velocity", "Dry voice", 1.7, "Olive, brass, and a serif are now a regional costume.", "Keep the colors only if the grid, the crop, and the sentence are stricter than the neighbors.", "Name the one rule the other capitals are breaking.", "This stops a moodboard from being mistaken for positioning. Ask which rule is actually theirs."),
    _hook("balkans", 20, "Stop promising the region in a drone shot.", "Pattern Interrupt", "Emerging", "Wind and a close voice", 1.0, "Coast, mountains, and a sunset read as a tourism board, not a house.", "Promise one guest, one room, one meal.", "Cut the aerials before the meeting.", "The drone shot is the shared cliché. Replacing it is the easiest visible difference in the deck."),
    _hook("balkans", 96, "The chef plated it. We did not add a filter.", "Behind-The-Scenes", "High velocity", "Kitchen sound", 2.2, "Food films in the region are graded until the plate looks like every other plate.", "Leave the color of the room. Correct nothing that the chef did not cook.", "Show the grade turned off, side by side.", "The line defends a quieter grade. Clients understand it when they see the filter they almost bought."),
    _hook("balkans", 420, "Your hotel film looks like the hotel across the border.", "Negative Friction", "Quiet", "Voice only", 1.9, "The same lobby stone, the same copper night shot, the same piano.", "Photograph the one material that exists only in that building.", "Open on that material for three seconds before the logo.", "Cross-border sameness is the actual competitive set. Treat the neighboring hotel as the reference, not a global campaign."),
    _hook("world", 8, "Pretty is now the easy part.", "Pattern Interrupt", "Breakout", "Dry voice, long pause", 2.0, "Tasteful frames are abundant. A point of view is not.", "Decide the one thing the work refuses, and show that refusal.", "Put the refusal on the first board, before the mockups.", "Use this when a client asks for something beautiful. Move the meeting to the decision the beauty is hiding."),
    _hook("world", 20, "Do not show the logo in the first second.", "Pattern Interrupt", "High velocity", "No music", 1.2, "Opening on the symbol trains people to skip it.", "Open on the problem the brand exists to fix. Land the mark after the proof.", "Time the logo to the fourth second and watch the hold.", "This is an edit note you can demonstrate in the room by covering the logo with a hand."),
    _hook("world", 96, "This is the color we refused.", "Behind-The-Scenes", "Emerging", "Studio room tone", 2.5, "Palettes are being presented as preferences instead of decisions.", "Show the rejected swatch and the competitor it belongs to.", "Leave the refused color in the appendix, labeled.", "A rejected color is more persuasive than a chosen one, because it shows the studio can say no."),
    _hook("world", 420, "The case study is four screens too long.", "Negative Friction", "Quiet", "Voice only", 1.5, "Process sections are repeating the same three steps in new nouns.", "Keep the constraint, the move, and the result. Cut the tour of the workshop.", "Rewrite one case study to a single screen before the pitch.", "Length is being mistaken for rigor. A shorter case study leaves room for the recommendation."),
]

DOMAINS = [
    _domain("varna_razgrad", 8, "diartis.studio", "дигитален маркетинг варна", 6, 2, "Position 6 is still the first screen. The pitch is a calmer page than the agencies above it, not a larger media budget."),
    _domain("varna_razgrad", 8, "meridian-dental.bg", "зъбни импланти разград", 3, 0, "Position 3 already takes the click. Attack the page: the offer, the type, the proof. Do not open the meeting with ad spend."),
    _domain("varna_razgrad", 96, "atelier-varna.bg", "интериорен дизайн варна", 4, 3, "Still on the first screen and still movable. One project, told through real materials, will read clearer than a grid of twelve thumbnails."),
    _domain("varna_razgrad", 420, "razgrad-studio.bg", "графичен дизайн разград", 9, -1, "Position 9 is the edge of the first screen. Search can support the pitch. The brand system has to carry the close."),
    _domain("bulgaria", 8, "diartis.studio", "creative agency sofia", 8, 1, "Position 8 is the bottom of the first screen. The page above the fold has to be quieter than the agencies sitting at 1 to 3."),
    _domain("bulgaria", 20, "paper-and-co.bg", "брандинг агенция софия", 2, 0, "Position 2 already owns the click. The deck should critique their page, not pretend the query is unclaimed."),
    _domain("bulgaria", 96, "northform.bg", "реклама за клиники", 5, 4, "A clinic query with room above it. The winning page will look like a practice, not like an agency selling to practices."),
    _domain("bulgaria", 420, "gridline.bg", "уеб дизайн софия", 12, -2, "Position 12 is off the first screen. Do not promise search as the lead channel until the page can earn a higher place."),
    _domain("greece_romania", 8, "aegean-form.gr", "digital agency thessaloniki", 5, 2, "Position 5 leaves a gap above. A plaster-white page with one project will look more specific than a full-service grid."),
    _domain("greece_romania", 20, "casa-atelier.ro", "agentie branding bucuresti", 3, 0, "Position 3 is taken. Beat them on the first screen of the work, not on a longer list of services."),
    _domain("greece_romania", 96, "plasterstudio.gr", "interior studio athens", 7, 1, "Position 7 is still visible. The hotels above are sharing one beige lookbook. A material-led page is the opening."),
    _domain("greece_romania", 420, "nordclinic.ro", "fatete dentare bucuresti", 4, -2, "Position 4 on a treatment query. The click is going to turquoise clinic templates. The pitch is the page that does not look like a clinic template."),
    _domain("balkans", 8, "diartis.studio", "balkan branding studio", 11, 3, "Position 11 is off the first screen. Lead the meeting with the work. Let search be a later chapter."),
    _domain("balkans", 20, "adria-house.hr", "boutique hotel design", 4, 0, "Position 4 is the competitive set for a hotel identity. Their page is the reference to be quieter than."),
    _domain("balkans", 96, "sava-atelier.rs", "branding agency belgrade", 6, 2, "Position 6 is reachable. The difference to show is the grid, because the olive palette is already shared."),
    _domain("balkans", 420, "skopje-form.mk", "design studio skopje", 8, -1, "Position 8 still sits on the first screen. One named material will distinguish the work faster than a new symbol."),
    _domain("world", 8, "diartis.studio", "boutique branding studio", 14, 2, "Position 14 is not the pitch. The deck should not pretend search is how this client will be won."),
    _domain("world", 20, "quietform.co", "editorial website design", 4, 0, "Position 4 is the reference for editorial web. Study their margins, then make one decision they are unwilling to make."),
    _domain("world", 96, "atelier-index.com", "brand identity studio", 9, 5, "Position 9 after a move up. The page is being rewarded. Keep the structure and change the color they are using as a wash."),
    _domain("world", 420, "marginandco.com", "luxury brand studio", 6, -1, "Position 6 is the middle of the first screen. Luxury queries punish sameness. Lead with the refusal, not the moodboard."),
]


def _check() -> None:
    for bucket in (VISUALS, HOOKS, DOMAINS):
        unknown = {row["region"] for row in bucket} - REGION_IDS
        if unknown:
            raise ValueError(f"Unknown regions in baseline: {unknown}")
    for row in VISUALS:
        if len(row["hex_codes"]) != 5 or any(_HEX.match(color) is None for color in row["hex_codes"]):
            raise ValueError(f"Palette must be five HEX colors: {row['ad_format']}")


def seed_if_empty() -> bool:
    _check()
    init_db()
    if table_count("visual_trends"):
        return False
    with connect() as conn:
        for row in VISUALS:
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
                },
                conn,
            )
    return True


if __name__ == "__main__":
    print("seeded" if seed_if_empty() else "already populated")
