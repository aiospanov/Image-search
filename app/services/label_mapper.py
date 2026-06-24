import asyncio
import time
from typing import Optional

import httpx

from app.config import settings
from app.db.database import get_pool

# In-memory cache: {label_en: terms_ru}
_cache: dict[str, list[str]] = {}
_cache_loaded_at: float = 0.0
_cache_lock = asyncio.Lock()


async def _load_cache() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT label_en, terms_ru FROM label_synonyms")
    global _cache, _cache_loaded_at
    _cache = {row["label_en"]: list(row["terms_ru"]) for row in rows}
    _cache_loaded_at = time.monotonic()


async def _ensure_cache() -> None:
    async with _cache_lock:
        if time.monotonic() - _cache_loaded_at > settings.label_cache_ttl_seconds:
            await _load_cache()


async def _translate_fallback(label_en: str) -> Optional[str]:
    """Translate via Google Translate API as fallback (FR-08)."""
    if not settings.google_translate_api_key:
        return None
    url = "https://translation.googleapis.com/language/translate/v2"
    params = {
        "q": label_en,
        "source": "en",
        "target": "ru",
        "key": settings.google_translate_api_key,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        return resp.json()["data"]["translations"][0]["translatedText"]
    except Exception:
        return None


async def map_labels(labels_en: list[str]) -> list[str]:
    """
    Map English labels to Russian catalog terms (FR-07, FR-08).
    Returns flat deduplicated list of Russian terms.
    """
    await _ensure_cache()

    russian_terms: list[str] = []
    fallback_tasks = []
    unmapped: list[str] = []

    for label in labels_en:
        terms = _cache.get(label.lower())
        if terms:
            russian_terms.extend(terms)
        else:
            unmapped.append(label)

    if unmapped:
        translated = await asyncio.gather(*[_translate_fallback(l) for l in unmapped])
        for term in translated:
            if term:
                russian_terms.append(term)

    # deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for t in russian_terms:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result
