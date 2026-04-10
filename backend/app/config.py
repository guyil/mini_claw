from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 数据库 ----
    database_url: str = "postgresql+asyncpg://mclaw:mclaw_dev_pass@localhost:5432/mclaw"

    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "")

    @property
    def database_url_psycopg(self) -> str:
        """langgraph-checkpoint-postgres 需要 psycopg 格式的连接串"""
        return self.database_url.replace("postgresql+asyncpg", "postgresql")

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/0"

    # ---- JWT ----
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # ---- LLM 默认配置 ----
    default_model: str = "gemini/gemini-2.0-flash"
    default_temperature: float = 0.7
    litellm_api_base: str | None = None
    litellm_api_key: str | None = None

    # ---- 飞书 OAuth ----
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_redirect_uri: str = "http://localhost:3000/auth/feishu/callback"
    feishu_domain: str = "feishu"

    # ---- 默认 Bot 配置（无 DB 时使用）----
    default_bot_soul: str = (
        "你是「小爪」，一个跨境电商领域的 AI 助手。\n\n"
        "## 核心原则\n"
        "- 真正有用，而不是表演有用。跳过客套话，直接解决问题。\n"
        "- 有自己的专业判断。你可以不同意、有偏好、指出问题。助手不等于没主见。\n"
        "- 先自己想办法。查记忆、读上下文、用工具，然后再问用户。"
        "目标是带着答案回来，而不是带着问题。\n"
        "- 通过能力赢得信任。对内部操作大胆（查数据、分析、记录），"
        "对外部操作谨慎（发消息、调用第三方）。\n\n"
        "## 专业领域\n"
        "选品分析、竞品调研、Listing 优化、广告策略、运营数据解读。\n\n"
        "## 会话连续性\n"
        "每次对话你都是全新开始。系统会自动加载你的记忆和近期工作日志，"
        "这就是你的连续性。主动使用它们。"
    )
    default_bot_instructions: str = (
        "1. 回答要结构化，善用表格和列表\n"
        "2. 涉及数据判断时说明数据来源和置信度\n"
        "3. 主动记录用户偏好和关键发现到记忆"
    )

    # ---- Perplexity (网络搜索) ----
    perplexity_api_key: str = ""

    # ---- Sandbox ----
    sandbox_enabled: bool = True
    sandbox_image: str = "mclaw-sandbox:latest"
    sandbox_max_active: int = 10
    sandbox_idle_timeout_minutes: int = 10

    # ---- 定时任务调度器 ----
    scheduler_enabled: bool = True
    scheduler_max_concurrent_jobs: int = 3
    scheduler_job_timeout_seconds: int = 120
    scheduler_max_consecutive_errors: int = 5

    # ---- 飞书工具组开关 ----
    feishu_tools_doc: bool = True
    feishu_tools_wiki: bool = True
    feishu_tools_drive: bool = True
    feishu_tools_chat: bool = True
    feishu_tools_bitable: bool = True
    feishu_tools_perm: bool = False
    feishu_tools_calendar: bool = True
    feishu_tools_task: bool = True


settings = Settings()
