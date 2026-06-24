# Image Search — MVP

Поиск товаров по изображению для маркетплейса. Реализует все `Must`-требования PRD v1.0.

## Поток данных

```
POST /api/search/image (jpg/png/webp, ≤10 MB)
  → Pillow: сжатие до 1 МБ
  → Google Vision API: LABEL_DETECTION, confidence ≥ 0.70, топ-5
  → label_mapper: словарь EN→RU (кэш 1 ч) + Google Translate fallback
  → Elasticsearch: multi_match + fuzziness:AUTO + фильтр in_stock
  → PostgreSQL: обогащение данными товара
  ← {products: [...], applied_labels: [...]}
```

## Структура проекта

```
app/
  main.py              # FastAPI приложение
  config.py            # Настройки из .env
  api/search.py        # POST /api/search/image + rate limiting
  services/
    vision_service.py  # Google Vision API + retry + сжатие фото
    label_mapper.py    # Словарь EN→RU + Translate fallback + кэш
    image_search.py    # Elasticsearch multi_match + PostgreSQL enrich
  db/database.py       # asyncpg connection pool
migrations/
  001_create_label_synonyms.sql  # Таблица словаря (50 категорий-seed)
  002_create_products.sql        # Таблица товаров
tests/                 # pytest + pytest-asyncio
```

## Быстрый старт

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Настроить окружение
cp .env.example .env
# Заполнить GOOGLE_VISION_API_KEY, POSTGRES_DSN, ELASTICSEARCH_URL

# 3. Применить миграции
psql $POSTGRES_DSN -f migrations/001_create_label_synonyms.sql
psql $POSTGRES_DSN -f migrations/002_create_products.sql

# 4. Запустить сервер
uvicorn app.main:app --reload

# 5. Тесты
pytest tests/
```

## Конфигурация (.env)

| Переменная | По умолчанию | Описание |
|------------|-------------|---------|
| `GOOGLE_VISION_API_KEY` | — | Обязательно |
| `GOOGLE_TRANSLATE_API_KEY` | — | Для fallback-перевода |
| `POSTGRES_DSN` | `postgresql://...` | Строка подключения |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | |
| `ELASTICSEARCH_INDEX` | `products` | |
| `RATE_LIMIT_REQUESTS` | `10` | Запросов с одного IP в минуту |
| `VISION_CONFIDENCE_THRESHOLD` | `0.70` | Минимальный порог уверенности |
| `LABEL_CACHE_TTL_SECONDS` | `3600` | TTL кэша словаря |

## API

### `POST /api/search/image`

**Request:** `multipart/form-data`, поле `file` — jpg/png/webp ≤ 10 МБ.

**Response 200:**
```json
{
  "products": [
    {"id": "sku-123", "name": "Кроссовки Nike Air", "price": 7990, "image_url": "...", "category": "Обувь", "brand": "Nike", "in_stock": true}
  ],
  "applied_labels": ["кроссовки", "кеды"]
}
```

**Коды ошибок:**
| Код | Причина |
|-----|---------|
| 413 | Файл > 10 МБ |
| 415 | Неподдерживаемый формат |
| 429 | Rate limit (10 запросов/мин с IP) |
| 503 | Google Vision API недоступен |

## Elasticsearch — требования к индексу

Индекс `products` должен содержать поля: `name`, `description`, `category`, `brand`, `in_stock`.

```bash
# Пример создания индекса
curl -X PUT http://localhost:9200/products -H 'Content-Type: application/json' -d '{
  "mappings": {
    "properties": {
      "id":          {"type": "keyword"},
      "name":        {"type": "text", "analyzer": "russian"},
      "description": {"type": "text", "analyzer": "russian"},
      "category":    {"type": "text", "analyzer": "russian"},
      "brand":       {"type": "text"},
      "in_stock":    {"type": "boolean"}
    }
  }
}'
```
