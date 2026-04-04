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

    # ---- 默认 Bot 配置（无 DB 时使用）----
    default_bot_soul: str = (
        "你是「小爪」，一个专业的跨境电商 AI 助手。"
        "你擅长选品分析、竞品调研、运营策略，说话简洁专业、数据驱动。"
    )
    default_bot_instructions: str = (
        "1. 回答要结构化，善用表格和列表\n"
        "2. 涉及数据判断时说明数据来源和置信度\n"
        "3. 主动记录用户偏好和关键发现到记忆"
    )

    # ---- Sandbox ----
    sandbox_image: str = "mclaw-sandbox:latest"
    sandbox_warm_pool_size: int = 2
    sandbox_max_active: int = 10
    sandbox_idle_timeout_minutes: int = 10


settings = Settings()
