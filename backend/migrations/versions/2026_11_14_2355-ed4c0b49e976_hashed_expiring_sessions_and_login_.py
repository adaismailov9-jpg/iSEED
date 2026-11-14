"""hashed expiring sessions and login failures

Revision ID: ed4c0b49e976
Revises: 4efcd4797c98
Create Date: 2026-11-14 23:55:24.840273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed4c0b49e976'
down_revision: Union[str, Sequence[str], None] = '4efcd4797c98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Sessions keep a hash of the token and expire; wrong PINs are recorded for the /login limit."""
    # Existing rows hold plain-text tokens and no expiry: drop them, users simply sign in again.
    op.execute("DELETE FROM sessions")
    op.alter_column("sessions", "token", new_column_name="token_hash")
    op.add_column("sessions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_check_constraint(op.f("ck_sessions_token_is_hash"), "sessions", "token_hash ~ '^[0-9a-f]{64}$'")

    op.create_table(
        "login_failures",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_failures")),
    )
    op.create_index("ix_login_failures_name_at", "login_failures", ["name", "at"])
    op.create_index("ix_login_failures_ip_at", "login_failures", ["ip", "at"])


def downgrade() -> None:
    op.drop_index("ix_login_failures_ip_at", table_name="login_failures")
    op.drop_index("ix_login_failures_name_at", table_name="login_failures")
    op.drop_table("login_failures")
    # Hashed tokens cannot be turned back into tokens: drop the sessions, users sign in again.
    op.execute("DELETE FROM sessions")
    op.drop_constraint(op.f("ck_sessions_token_is_hash"), "sessions", type_="check")
    op.drop_column("sessions", "expires_at")
    op.alter_column("sessions", "token_hash", new_column_name="token")
