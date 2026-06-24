import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _jpeg_bytes() -> bytes:
    img = Image.new("RGB", (200, 200), color=(0, 128, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200


def test_image_search_invalid_format():
    resp = client.post(
        "/api/search/image",
        files={"file": ("photo.gif", b"GIF89a", "image/gif")},
    )
    assert resp.status_code == 415


def test_image_search_too_large():
    big = b"x" * (11 * 1024 * 1024)
    resp = client.post(
        "/api/search/image",
        files={"file": ("photo.jpg", big, "image/jpeg")},
    )
    assert resp.status_code == 413


def test_image_search_no_labels_returns_friendly_message():
    from app.services.vision_service import VisionLabel

    with patch("app.api.search.get_labels", new=AsyncMock(return_value=[])):
        resp = client.post(
            "/api/search/image",
            files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["products"] == []
    assert "message" in data


def test_image_search_vision_api_unavailable():
    from app.services.vision_service import VisionServiceError

    with patch("app.api.search.get_labels", new=AsyncMock(side_effect=VisionServiceError("down"))):
        resp = client.post(
            "/api/search/image",
            files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
        )
    assert resp.status_code == 503


def test_image_search_success():
    from app.services.vision_service import VisionLabel

    fake_labels = [VisionLabel("sneakers", 0.95)]
    fake_products = [{"id": "sku-1", "name": "Кроссовки", "price": 3000}]

    with patch("app.api.search.get_labels", new=AsyncMock(return_value=fake_labels)):
        with patch("app.api.search.map_labels", new=AsyncMock(return_value=["кроссовки"])):
            with patch("app.api.search.search_products", new=AsyncMock(return_value=(fake_products, ["кроссовки"]))):
                resp = client.post(
                    "/api/search/image",
                    files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
                )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["products"]) == 1
    assert data["applied_labels"] == ["кроссовки"]
