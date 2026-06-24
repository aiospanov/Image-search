"""
Mock Vision service — used when USE_MOCK=true and no GOOGLE_VISION_API_KEY is set.
Analyses basic image properties (dominant color, aspect ratio) and returns
a small set of plausible labels so the full pipeline can be exercised end-to-end.
"""

import io
import random

from PIL import Image

from app.services.vision_service import VisionLabel

# Colour-to-category hints (very rough heuristic, enough for a hypothesis test)
_COLOR_HINTS: list[tuple[tuple[int, int, int], list[str]]] = [
    ((0, 0, 128), ["jeans", "trousers"]),          # dark blue
    ((0, 0, 200), ["jeans", "jacket"]),             # blue
    ((200, 200, 200), ["laptop", "smartphone"]),    # grey / silver
    ((0, 0, 0), ["smartphone", "headphones"]),      # black
    ((255, 255, 255), ["sneakers", "shirt"]),        # white
    ((139, 69, 19), ["handbag", "boot"]),            # brown
    ((34, 139, 34), ["jacket", "backpack"]),         # green
    ((255, 0, 0), ["sneakers", "t-shirt"]),          # red
]

_DEFAULT_LABELS = ["sneakers", "jacket", "smartphone", "handbag", "watch"]


def _dominant_color(img: Image.Image) -> tuple[int, int, int]:
    small = img.convert("RGB").resize((50, 50))
    pixels = list(small.getdata())
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)
    return r, g, b


def _color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    return ((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2 + (c1[2]-c2[2])**2) ** 0.5


def mock_get_labels(image_bytes: bytes) -> list[VisionLabel]:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        dom = _dominant_color(img)

        best_labels = _DEFAULT_LABELS
        best_dist = float("inf")
        for color, labels in _COLOR_HINTS:
            dist = _color_distance(dom, color)
            if dist < best_dist:
                best_dist = dist
                best_labels = labels

        # Add a random extra label for variety
        extra = random.choice([l for l in _DEFAULT_LABELS if l not in best_labels])
        labels_en = (best_labels + [extra])[:5]

    except Exception:
        labels_en = _DEFAULT_LABELS[:3]

    return [
        VisionLabel(description=label, confidence=round(random.uniform(0.75, 0.97), 2))
        for label in labels_en
    ]
