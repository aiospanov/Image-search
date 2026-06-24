from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.image_search import search_products


@pytest.mark.asyncio
async def test_returns_empty_for_no_terms():
    products, labels = await search_products([])
    assert products == []
    assert labels == []


@pytest.mark.asyncio
async def test_search_returns_products_sorted_by_score():
    es_response = {
        "hits": {
            "hits": [
                {"_source": {"id": "sku-1", "name": "Кроссовки Nike"}, "_score": 2.5},
                {"_source": {"id": "sku-2", "name": "Кеды Adidas"}, "_score": 1.8},
            ]
        }
    }

    fake_pg_rows = [
        {"id": "sku-1", "name": "Кроссовки Nike", "price": 5000, "image_url": "", "category": "Обувь", "brand": "Nike", "in_stock": True},
        {"id": "sku-2", "name": "Кеды Adidas", "price": 4500, "image_url": "", "category": "Обувь", "brand": "Adidas", "in_stock": True},
    ]

    mock_es = AsyncMock()
    mock_es.search = AsyncMock(return_value=es_response)

    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=fake_pg_rows)
    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()))

    with patch("app.services.image_search.get_es", return_value=mock_es):
        with patch("app.services.image_search.get_pool", AsyncMock(return_value=mock_pool)):
            products, labels = await search_products(["кроссовки", "обувь"])

    assert len(products) == 2
    assert products[0]["id"] == "sku-1"


@pytest.mark.asyncio
async def test_returns_empty_products_with_labels_on_no_hits():
    es_response = {"hits": {"hits": []}}

    mock_es = AsyncMock()
    mock_es.search = AsyncMock(return_value=es_response)

    with patch("app.services.image_search.get_es", return_value=mock_es):
        products, labels = await search_products(["кроссовки"])

    assert products == []
    assert "кроссовки" in labels
