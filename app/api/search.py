import time
from collections import defaultdict

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.label_mapper import map_labels
from app.services.vision_service import VisionServiceError, get_labels

router = APIRouter(prefix="/api/search", tags=["search"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    window = settings.rate_limit_window_seconds
    _rate_buckets[ip] = [t for t in _rate_buckets[ip] if now - t < window]
    if len(_rate_buckets[ip]) >= settings.rate_limit_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много запросов. Попробуйте через минуту.",
        )
    _rate_buckets[ip].append(now)


def _do_search(russian_terms: list[str]):
    if settings.use_mock:
        from app.services.mock_search import mock_search_products
        return mock_search_products(russian_terms)
    else:
        import asyncio
        from app.services.image_search import search_products
        return search_products(russian_terms)


async def _get_labels_safe(image_bytes: bytes):
    if settings.use_mock and not settings.google_vision_api_key:
        from app.services.mock_vision import mock_get_labels
        return mock_get_labels(image_bytes)
    return await get_labels(image_bytes)


@router.post("/image")
async def image_search(request: Request, file: UploadFile = File(...)):
    """
    POST /api/search/image
    Accepts jpg/png/webp up to 10 MB, returns matched products and applied labels.
    Set USE_MOCK=true in .env to run without real databases or Google API key.
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются форматы: jpg, png, webp.",
        )

    image_bytes = await file.read()

    if len(image_bytes) > settings.max_image_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл слишком большой. Максимальный размер — 10 МБ.",
        )

    try:
        vision_labels = await _get_labels_safe(image_bytes)
    except VisionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    if not vision_labels:
        return JSONResponse(
            {
                "products": [],
                "applied_labels": [],
                "message": "Не удалось распознать товар на фото. Попробуйте другое изображение.",
            }
        )

    labels_en = [lbl.description for lbl in vision_labels]

    # Map labels EN→RU. In mock mode without translate key — skip gracefully.
    try:
        russian_terms = await map_labels(labels_en)
    except Exception:
        russian_terms = labels_en  # fallback: use English labels as-is

    result = _do_search(russian_terms)
    # mock_search_products returns tuple directly; search_products is a coroutine
    if hasattr(result, "__await__"):
        products, applied_labels = await result
    else:
        products, applied_labels = result

    if not products:
        return JSONResponse(
            {
                "products": [],
                "applied_labels": applied_labels,
                "message": "По этому фото ничего не найдено. Попробуйте другое изображение.",
            }
        )

    return {"products": products, "applied_labels": applied_labels}
