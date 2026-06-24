from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.search import router as search_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.use_mock:
        from app.db.database import close_pool, get_pool
        from app.services.image_search import get_es
        await get_pool()
        yield
        await close_pool()
        await get_es().close()
    else:
        yield


app = FastAPI(
    title="Image Search API",
    description="Поиск товаров по изображению — MVP",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(search_router)


@app.get("/health")
async def health():
    mode = "mock" if settings.use_mock else "production"
    return {"status": "ok", "mode": mode}
