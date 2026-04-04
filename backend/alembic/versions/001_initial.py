"""初始化数据库表结构

Revision ID: 001
Revises:
Create Date: 2026-04-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("is_admin", sa.Boolean, default=False),
        sa.Column("feishu_access_token", sa.String(500)),
        sa.Column("feishu_refresh_token", sa.String(500)),
        sa.Column("feishu_token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "bots",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "owner_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("soul", sa.Text, nullable=False),
        sa.Column("instructions", sa.Text),
        sa.Column("user_context", sa.Text),
        sa.Column("model_name", sa.String(100), default="openai/gpt-4o-mini"),
        sa.Column("temperature", sa.Float, default=0.7),
        sa.Column(
            "enabled_skills",
            sa.dialects.postgresql.ARRAY(sa.dialects.postgresql.UUID(as_uuid=True)),
        ),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(50)),
        sa.Column("version", sa.String(20), default="1.0.0"),
        sa.Column("instructions", sa.Text, nullable=False),
        sa.Column("required_tools", sa.dialects.postgresql.ARRAY(sa.String)),
        sa.Column("required_env_vars", sa.dialects.postgresql.ARRAY(sa.String)),
        sa.Column("input_schema", sa.dialects.postgresql.JSONB),
        sa.Column("output_schema", sa.dialects.postgresql.JSONB),
        sa.Column("scope", sa.String(20), default="global"),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
        ),
        sa.Column("source", sa.String(50)),
        sa.Column("source_url", sa.String(500)),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "skill_assets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "skill_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_binary", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "memories",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "bot_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("bots.id"),
            nullable=False,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536)),
        sa.Column("source", sa.String(50)),
        sa.Column("importance", sa.Float, default=0.5),
        sa.Column("memory_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_memories_bot_type", "memories", ["bot_id", "type"])
    op.create_index("idx_memories_bot_date", "memories", ["bot_id", "memory_date"])

    op.create_table(
        "tools",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200)),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("impl_type", sa.String(20), nullable=False),
        sa.Column("impl_config", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("parameters", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("requires_approval", sa.Boolean, default=False),
        sa.Column("risk_level", sa.String(10), default="low"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tools")
    op.drop_index("idx_memories_bot_date", table_name="memories")
    op.drop_index("idx_memories_bot_type", table_name="memories")
    op.drop_table("memories")
    op.drop_table("skill_assets")
    op.drop_table("skills")
    op.drop_table("bots")
    op.drop_table("users")
