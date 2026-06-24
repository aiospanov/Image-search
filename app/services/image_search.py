from elasticsearch import AsyncElasticsearch

from app.config import settings
from app.db.database import get_pool

_es: AsyncElasticsearch | None = None


def get_es() -> AsyncElasticsearch:
    global _es
    if _es is None:
        _es = AsyncElasticsearch(settings.elasticsearch_url)
    return _es


async def search_products(russian_terms: list[str]) -> tuple[list[dict], list[str]]:
    """
    Perform multi_match search in Elasticsearch (FR-10, FR-11, FR-12, FR-13).
    Returns (products, applied_labels).
    """
    if not russian_terms:
        return [], []

    query_string = " ".join(russian_terms)

    body = {
        "query": {
            "bool": {
                "must": {
                    "multi_match": {
                        "query": query_string,
                        "fields": ["name^3", "description", "category^2", "brand^2"],
                        "fuzziness": "AUTO",
                        "type": "best_fields",
                    }
                },
                "filter": {"term": {"in_stock": True}},
            }
        },
        "size": settings.search_max_results,
        "_source": ["id", "name", "price", "image_url", "category", "brand"],
    }

    es = get_es()
    response = await es.search(index=settings.elasticsearch_index, body=body)
    hits = response["hits"]["hits"]

    if not hits:
        return [], russian_terms

    skus = [h["_source"]["id"] for h in hits]
    scores = {h["_source"]["id"]: h["_score"] for h in hits}

    products = await _enrich_from_postgres(skus, scores)
    return products, russian_terms


async def _enrich_from_postgres(
    skus: list[str], scores: dict[str, float]
) -> list[dict]:
    """Fetch full product data from PostgreSQL ordered by ES relevance score."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, price, image_url, category, brand, in_stock
            FROM products
            WHERE id = ANY($1::text[])
            """,
            skus,
        )

    products = [dict(row) for row in rows]
    products.sort(key=lambda p: scores.get(p["id"], 0), reverse=True)
    return products
