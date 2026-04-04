from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化资源
    from app.services.sandbox_pool import SandboxPoolManager

    app.state.sandbox_pool = SandboxPoolManager(
        image=settings.sandbox_image,
        warm_pool_size=settings.sandbox_warm_pool_size,
        max_active=settings.sandbox_max_active,
        idle_timeout_minutes=settings.sandbox_idle_timeout_minutes,
    )
    await app.state.sandbox_pool.initialize()

    yield

    # 关闭时清理资源


app = FastAPI(
    title="跨境电商 AI 助手平台",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.api.auth import router as auth_router
from app.api.bots import router as bots_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.skills import router as skills_router

app.include_router(auth_router)
app.include_router(bots_router)
app.include_router(conversations_router)
app.include_router(skills_router)
app.include_router(chat_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
