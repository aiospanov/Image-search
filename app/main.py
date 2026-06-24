from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.search import router as search_router
from app.db.database import close_pool, get_pool
from app.services.image_search import get_es


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    await close_pool()
    es = get_es()
    await es.close()


app = FastAPI(
    title="Image Search API",
    description="Поиск товаров по изображению — MVP",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(search_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
