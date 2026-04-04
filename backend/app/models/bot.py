import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Bot(Base):
    __tablename__ = "bots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Soul: 人格定义（等价于 SOUL.md）
    soul: Mapped[str] = mapped_column(Text, nullable=False)

    # Agent Instructions: 工作指令（等价于 AGENTS.md）
    instructions: Mapped[str | None] = mapped_column(Text)

    # User Context: 用户画像（等价于 USER.md）
    user_context: Mapped[str | None] = mapped_column(Text)

    # 模型配置
    model_name: Mapped[str] = mapped_column(String(100), default="openai/gpt-4o-mini")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)

    # Skills 绑定 (UUID 数组)
    enabled_skills: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="bots", lazy="selectin")  # noqa: F821
