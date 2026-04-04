import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id"), nullable=False
    )

    # 记忆类型: long_term | daily | fact
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 语义搜索向量 (1536 维 — OpenAI text-embedding-3-small 兼容)
    embedding = mapped_column(Vector(1536))

    # 元数据
    source: Mapped[str | None] = mapped_column(String(50))
    importance: Mapped[float] = mapped_column(Float, default=0.5)

    # 时间
    memory_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "idx_memories_bot_type",
            "bot_id",
            "type",
        ),
        Index(
            "idx_memories_bot_date",
            "bot_id",
            "memory_date",
        ),
    )
