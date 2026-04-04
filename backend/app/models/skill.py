import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")

    # Skill 指令体（自然语言多步工作流）
    instructions: Mapped[str] = mapped_column(Text, nullable=False)

    # 依赖声明
    required_tools: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)
    required_env_vars: Mapped[list[str] | None] = mapped_column(ARRAY(String), default=list)

    # 输入输出规范
    input_schema: Mapped[dict | None] = mapped_column(JSONB)
    output_schema: Mapped[dict | None] = mapped_column(JSONB)

    # 权限与范围
    scope: Mapped[str] = mapped_column(String(20), default="global")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )

    # 来源（自建 / clawhub / lark-official-adapted）
    source: Mapped[str | None] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(String(500))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assets: Mapped[list["SkillAsset"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan", lazy="selectin"
    )


class SkillAsset(Base):
    __tablename__ = "skill_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_binary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    skill: Mapped["Skill"] = relationship(back_populates="assets")

    __table_args__ = (
        # 同一 skill 下文件名唯一
        {"comment": "Skill 附带的脚本和模板文件"},
    )
