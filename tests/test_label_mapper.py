from unittest.mock import AsyncMock, patch

import pytest

from app.services.label_mapper import map_labels


@pytest.mark.asyncio
async def test_map_known_labels():
    fake_cache = {"sneakers": ["кроссовки", "кеды"], "jacket": ["куртка", "жакет"]}
    with patch("app.services.label_mapper._ensure_cache", new=AsyncMock()):
        with patch("app.services.label_mapper._cache", fake_cache):
            result = await map_labels(["sneakers", "jacket"])

    assert "кроссовки" in result
    assert "куртка" in result


@pytest.mark.asyncio
async def test_fallback_translation_called_for_unknown_label():
    fake_cache = {}
    mock_translate = AsyncMock(return_value="худи")

    with patch("app.services.label_mapper._ensure_cache", new=AsyncMock()):
        with patch("app.services.label_mapper._cache", fake_cache):
            with patch("app.services.label_mapper._translate_fallback", new=mock_translate):
                result = await map_labels(["hoodie"])

    mock_translate.assert_awaited_once_with("hoodie")
    assert "худи" in result


@pytest.mark.asyncio
async def test_deduplication():
    # both labels map to overlapping terms
    fake_cache = {
        "shoe": ["обувь", "кроссовки"],
        "sneakers": ["кроссовки", "кеды"],
    }
    with patch("app.services.label_mapper._ensure_cache", new=AsyncMock()):
        with patch("app.services.label_mapper._cache", fake_cache):
            result = await map_labels(["shoe", "sneakers"])

    assert result.count("кроссовки") == 1
