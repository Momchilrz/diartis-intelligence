"""Five-color palette extraction with a brand-tone fallback."""

from __future__ import annotations

import io
import re

import cv2
import numpy as np
import requests
from PIL import Image, UnidentifiedImageError
from sklearn.cluster import KMeans

from config import BRAND_PALETTE, SOURCE_BRAND, SOURCE_COLOR
from services.net import UrlError, fetch_public

_HEX = re.compile(r"^#[0-9A-F]{6}$")


def safe_hex(value: str) -> str:
    text = (value or "").strip().upper()
    if text and not text.startswith("#"):
        text = f"#{text}"
    return text if _HEX.match(text) else "#E2E2DC"


def _hex_from_rgb(rgb: np.ndarray) -> str:
    channels = [int(max(0, min(255, round(float(channel))))) for channel in rgb[:3]]
    return "#{:02X}{:02X}{:02X}".format(*channels)


def extract_palette(image: Image.Image, n_colors: int = 5) -> list[str]:
    rgb = np.array(image.convert("RGB"))
    height, width = rgb.shape[:2]
    longest = max(height, width)
    if longest > 140:
        scale = 140 / longest
        rgb = cv2.resize(
            rgb,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    pixels = lab.reshape(-1, 3).astype(np.float32)
    if len(pixels) > 6000:
        index = np.linspace(0, len(pixels) - 1, 6000).astype(int)
        pixels = pixels[index]
    unique = np.unique(pixels.astype(np.uint8), axis=0)
    clusters = min(n_colors, len(unique))
    if clusters < 1:
        return list(BRAND_PALETTE)
    model = KMeans(n_clusters=clusters, n_init=10, random_state=7)
    labels = model.fit_predict(pixels)
    counts = np.bincount(labels, minlength=clusters)
    order = np.argsort(-counts)
    centers = np.clip(model.cluster_centers_, 0, 255).astype(np.uint8)
    centers_rgb = cv2.cvtColor(centers.reshape(-1, 1, 3), cv2.COLOR_LAB2RGB).reshape(-1, 3)
    colors = [_hex_from_rgb(centers_rgb[index]) for index in order]
    for tone in BRAND_PALETTE:
        if len(colors) >= n_colors:
            break
        if tone not in colors:
            colors.append(tone)
    return [safe_hex(color) for color in colors[:n_colors]]


def _result(colors: list[str], *, ok: bool, source: str, note: str) -> dict:
    return {"ok": ok, "colors": colors[:5], "source": source, "note": note}


def _from_bytes(content: bytes) -> dict:
    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return _result(
            list(BRAND_PALETTE),
            ok=False,
            source=SOURCE_BRAND,
            note="The image did not open. Showing the diArtis brand tones so the palette stays usable.",
        )
    try:
        colors = extract_palette(image)
    except Exception:
        return _result(
            list(BRAND_PALETTE),
            ok=False,
            source=SOURCE_BRAND,
            note="The palette could not be clustered. Showing the diArtis brand tones.",
        )
    return _result(colors, ok=True, source=SOURCE_COLOR, note="Five colors ordered by their share of the frame.")


def extract_from_bytes(content: bytes) -> dict:
    if not content:
        return _result(
            list(BRAND_PALETTE),
            ok=False,
            source=SOURCE_BRAND,
            note="No image arrived. Showing the diArtis brand tones.",
        )
    if len(content) > 8_000_000:
        return _result(
            list(BRAND_PALETTE),
            ok=False,
            source=SOURCE_BRAND,
            note="That file is over 8 MB. Showing the diArtis brand tones.",
        )
    return _from_bytes(content)


def extract_from_url(url: str) -> dict:
    try:
        fetched = fetch_public(url, timeout=12, max_bytes=8_000_000)
    except UrlError as exc:
        return _result(list(BRAND_PALETTE), ok=False, source=SOURCE_BRAND, note=str(exc))
    except requests.RequestException:
        return _result(
            list(BRAND_PALETTE),
            ok=False,
            source=SOURCE_BRAND,
            note="The image address did not respond. Showing the diArtis brand tones.",
        )
    if fetched["status"] >= 400 or not fetched["content"]:
        return _result(
            list(BRAND_PALETTE),
            ok=False,
            source=SOURCE_BRAND,
            note="The image address did not return a file. Showing the diArtis brand tones.",
        )
    return _from_bytes(fetched["content"])
