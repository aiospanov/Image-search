import asyncio
import io
from dataclasses import dataclass

import httpx
from PIL import Image

from app.config import settings


@dataclass
class VisionLabel:
    description: str
    confidence: float


class VisionServiceError(Exception):
    pass


def _compress_image(image_bytes: bytes) -> bytes:
    """Compress image to fit within compressed_image_size_bytes."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    output = io.BytesIO()
    quality = 85
    while quality >= 20:
        output.seek(0)
        output.truncate()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        if output.tell() <= settings.compressed_image_size_bytes:
            break
        quality -= 10

    return output.getvalue()


async def _call_vision_api(image_bytes: bytes) -> list[dict]:
    import base64

    encoded = base64.b64encode(image_bytes).decode()
    payload = {
        "requests": [
            {
                "image": {"content": encoded},
                "features": [{"type": "LABEL_DETECTION", "maxResults": 20}],
            }
        ]
    }
    url = f"https://vision.googleapis.com/v1/images:annotate?key={settings.google_vision_api_key}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()
    annotations = data["responses"][0].get("labelAnnotations", [])
    return annotations


async def get_labels(image_bytes: bytes) -> list[VisionLabel]:
    """
    Call Google Vision API with retry logic (FR-05, FR-06, NFR-04, NFR-05).
    Returns top labels with confidence >= threshold.
    """
    compressed = _compress_image(image_bytes)

    for attempt in range(2):
        try:
            annotations = await _call_vision_api(compressed)
            labels = [
                VisionLabel(description=a["description"], confidence=a["score"])
                for a in annotations
                if a["score"] >= settings.vision_confidence_threshold
            ]
            return labels[: settings.vision_top_labels]
        except httpx.HTTPError as exc:
            if attempt == 0:
                await asyncio.sleep(0.5)
            else:
                raise VisionServiceError(
                    "Google Vision API недоступен. Попробуйте позже."
                ) from exc

    return []
