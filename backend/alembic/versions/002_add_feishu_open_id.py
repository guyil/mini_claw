"""添加 feishu_open_id 字段

Revision ID: 002
Revises: 001
Create Date: 2026-04-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("feishu_open_id", sa.String(100), nullable=True))
    op.create_index("ix_users_feishu_open_id", "users", ["feishu_open_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_feishu_open_id", table_name="users")
    op.drop_column("users", "feishu_open_id")
