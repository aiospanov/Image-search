"""
Mock search backend — replaces Elasticsearch + PostgreSQL for hypothesis testing.
Activated when USE_MOCK=true in .env.
Loads products.json and does simple keyword search against the `tags` field.
"""

import json
from pathlib import Path

from app.config import settings

_products: list[dict] | None = None


def _load_products() -> list[dict]:
    global _products
    if _products is None:
        path = Path(settings.mock_data_path)
        _products = json.loads(path.read_text(encoding="utf-8"))
    return _products


def mock_search_products(russian_terms: list[str]) -> tuple[list[dict], list[str]]:
    """
    Score each product by how many query terms appear in its tags/name/category/brand.
    Returns only in_stock items, sorted by score, limited to search_max_results.
    """
    if not russian_terms:
        return [], []

    products = _load_products()
    scored: list[tuple[int, dict]] = []

    normalized_terms = [t.lower() for t in russian_terms]

    for product in products:
        if not product.get("in_stock"):
            continue

        searchable = " ".join([
            product.get("name", ""),
            product.get("category", ""),
            product.get("brand", ""),
            " ".join(product.get("tags", [])),
        ]).lower()

        score = sum(1 for term in normalized_terms if term in searchable)
        if score > 0:
            scored.append((score, product))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [p for _, p in scored[: settings.search_max_results]]

    # Strip internal `tags` field from the response
    clean = [
        {k: v for k, v in p.items() if k != "tags"}
        for p in results
    ]
    return clean, russian_terms
