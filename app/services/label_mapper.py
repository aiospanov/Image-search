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
    global _cache, _cache_loaded_at
    if settings.use_mock:
        _cache = _BUILTIN_DICT.copy()
    else:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT label_en, terms_ru FROM label_synonyms")
        _cache = {row["label_en"]: list(row["terms_ru"]) for row in rows}
    _cache_loaded_at = time.monotonic()


# Built-in dictionary used in mock mode (mirrors 001_create_label_synonyms.sql)
_BUILTIN_DICT: dict[str, list[str]] = {
    "sneakers":          ["кроссовки", "кеды"],
    "shoes":             ["обувь", "туфли", "ботинки"],
    "boot":              ["ботинки", "сапоги"],
    "sandal":            ["сандалии", "босоножки"],
    "jacket":            ["куртка", "жакет", "ветровка"],
    "coat":              ["пальто", "шуба"],
    "dress":             ["платье", "сарафан"],
    "shirt":             ["рубашка", "сорочка"],
    "t-shirt":           ["футболка", "майка"],
    "jeans":             ["джинсы", "брюки"],
    "trousers":          ["брюки", "штаны"],
    "shorts":            ["шорты"],
    "skirt":             ["юбка"],
    "sweater":           ["свитер", "джемпер", "пуловер"],
    "hoodie":            ["худи", "толстовка"],
    "handbag":           ["сумка", "сумочка"],
    "backpack":          ["рюкзак"],
    "wallet":            ["кошелёк", "портмоне"],
    "belt":              ["ремень", "пояс"],
    "hat":               ["шапка", "кепка", "шляпа"],
    "sunglasses":        ["солнцезащитные очки", "очки"],
    "watch":             ["часы", "наручные часы"],
    "ring":              ["кольцо"],
    "necklace":          ["ожерелье", "цепочка"],
    "bracelet":          ["браслет"],
    "earring":           ["серьги"],
    "smartphone":        ["смартфон", "телефон", "мобильный"],
    "laptop":            ["ноутбук", "лэптоп"],
    "tablet":            ["планшет"],
    "headphones":        ["наушники"],
    "speaker":           ["колонка", "акустика"],
    "camera":            ["фотоаппарат", "камера"],
    "keyboard":          ["клавиатура"],
    "mouse":             ["мышь", "мышка"],
    "monitor":           ["монитор", "экран"],
    "television":        ["телевизор", "тв"],
    "sofa":              ["диван", "кресло"],
    "chair":             ["стул", "кресло"],
    "table":             ["стол", "столик"],
    "lamp":              ["лампа", "светильник", "люстра"],
    "bookcase":          ["книжный шкаф", "стеллаж"],
    "pillow":            ["подушка"],
    "blanket":           ["плед", "одеяло"],
    "cup":               ["кружка", "чашка"],
    "bottle":            ["бутылка", "термос"],
    "toy":               ["игрушка"],
    "bicycle":           ["велосипед"],
    "fitness equipment": ["тренажёр", "спортивный инвентарь"],
    "yoga mat":          ["коврик для йоги", "спортивный коврик"],
    "book":              ["книга"],
}


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
