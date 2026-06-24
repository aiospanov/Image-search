from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

_static = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_static), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(_static / "index.html")


@app.get("/health")
async def health():
    mode = "mock" if settings.use_mock else "production"
    return {"status": "ok", "mode": mode}
