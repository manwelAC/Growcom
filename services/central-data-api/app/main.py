"""
Growcom Central Data API — Single Source of Truth.
Wraps H-pun/growtopia-api (items.dat parser, RTTEX converter, Wiki scraper, and live status).
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from app.api.v1 import converter, items, wiki
from app.config import settings
from app.core.items_parser import items_index

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.textures_dir.mkdir(parents=True, exist_ok=True)
    items_index.load(settings.items_dat_path)
    yield


app = FastAPI(
    title="Growcom Central Data API",
    description="Centralized microservice wrapping H-pun/growtopia-api for the Growcom Discord ecosystem.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(items.router, prefix="/api/v1")
app.include_router(wiki.router, prefix="/api/v1")
app.include_router(converter.router, prefix="/api/v1")


@app.api_route("/", methods=["GET", "HEAD"], tags=["system"])
@app.api_route("/api/v1/health", methods=["GET", "HEAD"], tags=["system"])
async def health_check() -> dict:
    return {
        "status": "ok",
        "service": "Growcom Events by Manwel",
        "items_dat_version": items_index.version,
        "items_loaded": len(items_index.items_by_id),
        "using_fallback_catalog": items_index.using_fallback,
    }
