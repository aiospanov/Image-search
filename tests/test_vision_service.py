import io
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from app.services.vision_service import VisionServiceError, VisionLabel, get_labels


def _make_image_bytes() -> bytes:
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_get_labels_returns_filtered_labels():
    fake_annotations = [
        {"description": "sneakers", "score": 0.95},
        {"description": "shoe", "score": 0.88},
        {"description": "background", "score": 0.50},  # below threshold
    ]
    with patch("app.services.vision_service._call_vision_api", new=AsyncMock(return_value=fake_annotations)):
        labels = await get_labels(_make_image_bytes())

    assert len(labels) == 2
    assert labels[0].description == "sneakers"
    assert all(lbl.confidence >= 0.70 for lbl in labels)


@pytest.mark.asyncio
async def test_get_labels_returns_max_top_n():
    fake_annotations = [{"description": f"label{i}", "score": 0.9} for i in range(10)]
    with patch("app.services.vision_service._call_vision_api", new=AsyncMock(return_value=fake_annotations)):
        labels = await get_labels(_make_image_bytes())

    assert len(labels) <= 5


@pytest.mark.asyncio
async def test_get_labels_retries_on_failure():
    import httpx

    call_count = 0

    async def flaky_api(image_bytes):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.HTTPError("timeout")
        return [{"description": "jacket", "score": 0.91}]

    with patch("app.services.vision_service._call_vision_api", new=flaky_api):
        with patch("asyncio.sleep", new=AsyncMock()):
            labels = await get_labels(_make_image_bytes())

    assert call_count == 2
    assert labels[0].description == "jacket"


@pytest.mark.asyncio
async def test_get_labels_raises_after_two_failures():
    import httpx

    async def always_fail(image_bytes):
        raise httpx.HTTPError("network error")

    with patch("app.services.vision_service._call_vision_api", new=always_fail):
        with patch("asyncio.sleep", new=AsyncMock()):
            with pytest.raises(VisionServiceError):
                await get_labels(_make_image_bytes())
