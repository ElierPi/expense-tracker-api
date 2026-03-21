"""Initial schema. Frozen DDL; does not import application models."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.UniqueConstraint("owner_id", "name", name="uq_category_owner_name"),
        sa.UniqueConstraint("id", "owner_id", name="uq_category_id_owner"),
    )
    op.create_index("ix_categories_owner_id", "categories", ["owner_id"])
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("kind", sa.String(7), nullable=False),
        sa.Column("description", sa.String(280), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["category_id", "owner_id"],
            ["categories.id", "categories.owner_id"],
            name="fk_transaction_category_owner",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("amount > 0", name="ck_transaction_positive_amount"),
        sa.CheckConstraint("kind IN ('income', 'expense')", name="ck_transaction_kind"),
        sa.CheckConstraint("currency IN ('COP', 'USD', 'EUR', 'GBP', 'MXN')", name="ck_currency"),
    )
    op.create_index("ix_transaction_owner_date", "transactions", ["owner_id", "occurred_on"])


def downgrade():
    op.drop_table("transactions")
    op.drop_table("categories")
    op.drop_table("users")
