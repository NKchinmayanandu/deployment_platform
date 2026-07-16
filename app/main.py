from contextlib import asynccontextmanager

from arq.connections import RedisSettings, create_pool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.applications import router as applications_router
from app.api.deployments import router as deployments_router
from app.core.config import settings
from app.utils.logging import setup_logging


from arq.connections import RedisSettings, create_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    app.state.arq_pool = await create_pool(
        RedisSettings.from_dsn(settings.REDIS_URL)
    )

    yield

    await app.state.arq_pool.aclose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(applications_router, prefix=settings.API_PREFIX)
app.include_router(deployments_router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "version": settings.VERSION}