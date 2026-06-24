import time
from collections import defaultdict

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.image_search import search_products
from app.services.label_mapper import map_labels
from app.services.vision_service import VisionServiceError, get_labels

router = APIRouter(prefix="/api/search", tags=["search"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Simple in-memory rate limiter: {ip: [(timestamp, count)]}
_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    window = settings.rate_limit_window_seconds
    bucket = _rate_buckets[ip]
    # Remove timestamps outside the window
    _rate_buckets[ip] = [t for t in bucket if now - t < window]
    if len(_rate_buckets[ip]) >= settings.rate_limit_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много запросов. Попробуйте через минуту.",
        )
    _rate_buckets[ip].append(now)


@router.post("/image")
async def image_search(request: Request, file: UploadFile = File(...)):
    """
    POST /api/search/image
    Accepts jpg/png/webp up to 10 MB, returns matched products and applied labels.
    """
    # Rate limiting (NFR-09)
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # Validate content type (FR-04)
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Поддерживаются форматы: jpg, png, webp.",
        )

    image_bytes = await file.read()

    # Validate file size (FR-01)
    if len(image_bytes) > settings.max_image_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Файл слишком большой. Максимальный размер — 10 МБ.",
        )

    # Analyse image (FR-05, FR-06)
    try:
        vision_labels = await get_labels(image_bytes)
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

    # Map labels to Russian (FR-07, FR-08)
    russian_terms = await map_labels(labels_en)

    # Search Elasticsearch (FR-10 – FR-13)
    products, applied_labels = await search_products(russian_terms)

    if not products:
        return JSONResponse(
            {
                "products": [],
                "applied_labels": applied_labels,
                "message": "По этому фото ничего не найдено. Попробуйте другое изображение.",
            }
        )

    return {"products": products, "applied_labels": applied_labels}
