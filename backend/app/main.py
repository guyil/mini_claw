from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv

load_dotenv("../.env")

# 确保系统代理不会拦截内部服务请求（LiteLLM 网关 / 飞书 API 等不需要走代理）
# 此处显式设置，优先级高于 macOS 系统代理设置。
_NO_PROXY_HOSTS = (
    "gateway.yw-aioa.com,"
    "open.feishu.cn,accounts.feishu.cn,open.larksuite.com,"
    "localhost,127.0.0.1,::1"
)
for _var in ("NO_PROXY", "no_proxy"):
    existing = os.environ.get(_var, "")
    if existing:
        os.environ[_var] = f"{existing},{_NO_PROXY_HOSTS}"
    else:
        os.environ[_var] = _NO_PROXY_HOSTS

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.sandbox_pool import SandboxPoolManager

    if settings.sandbox_enabled:
        pool = SandboxPoolManager(
            image=settings.sandbox_image,
            max_active=settings.sandbox_max_active,
            idle_timeout_minutes=settings.sandbox_idle_timeout_minutes,
        )
        app.state.sandbox_pool = pool
    else:
        app.state.sandbox_pool = None

    # 启动定时任务调度器
    scheduler = None
    if settings.scheduler_enabled:
        from app.services.scheduler_service import SchedulerService
        from app.tools.schedule_tools import set_scheduler_service

        scheduler = SchedulerService(
            max_concurrent=settings.scheduler_max_concurrent_jobs,
            job_timeout=settings.scheduler_job_timeout_seconds,
        )
        set_scheduler_service(scheduler)
        app.state.scheduler = scheduler
        await scheduler.start()

    yield

    # 关闭 Crawl4AI 浏览器实例
    from app.tools.web_tools import shutdown_crawler
    await shutdown_crawler()

    if scheduler:
        await scheduler.stop()

    if settings.sandbox_enabled and app.state.sandbox_pool:
        await app.state.sandbox_pool.shutdown()


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
from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.bots import router as bots_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.scheduled_jobs import router as scheduled_jobs_router
from app.api.skills import router as skills_router

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(bots_router)
app.include_router(conversations_router)
app.include_router(skills_router)
app.include_router(scheduled_jobs_router)
app.include_router(chat_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
