"""Initial schema: users, farms, predictions, knowledge base.

Matches app/db/models.py (ARCH §8.2). predictions_disease/yield carry the
nullable user_id column (anonymous predictions allowed); every table
mirrors the ORM exactly so `alembic upgrade head` and
`Base.metadata.create_all` produce identical schemas.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(64), nullable=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("preferred_language", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "farms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("district", sa.String(128), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("default_crop", sa.String(64), nullable=True),
        sa.Column("area_ha", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_farms_user_id", "farms", ["user_id"])

    op.create_table(
        "predictions_disease",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("image_url", sa.String(512), nullable=False),
        sa.Column("overlay_url", sa.String(512), nullable=False),
        sa.Column("crop", sa.String(64), nullable=False),
        sa.Column("disease_class", sa.String(128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("is_healthy", sa.Boolean(), nullable=False),
        sa.Column("severity_band", sa.String(32), nullable=False),
        sa.Column("severity_ratio_pct", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_predictions_disease_user_id", "predictions_disease", ["user_id"])
    op.create_index("ix_predictions_disease_crop", "predictions_disease", ["crop"])
    op.create_index(
        "ix_predictions_disease_disease_class", "predictions_disease", ["disease_class"]
    )

    op.create_table(
        "predictions_yield",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("crop", sa.String(64), nullable=False),
        sa.Column("district", sa.String(128), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("area_ha", sa.Float(), nullable=False),
        sa.Column("predicted_yield_tha", sa.Float(), nullable=False),
        sa.Column("interval_lower", sa.Float(), nullable=False),
        sa.Column("interval_upper", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_predictions_yield_user_id", "predictions_yield", ["user_id"])
    op.create_index("ix_predictions_yield_crop", "predictions_yield", ["crop"])
    op.create_index("ix_predictions_yield_district", "predictions_yield", ["district"])

    op.create_table(
        "disease_knowledge",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("class_id", sa.String(128), nullable=False, unique=True),
        sa.Column("crop", sa.String(64), nullable=False),
        sa.Column("disease_name", sa.String(128), nullable=False),
        sa.Column("is_healthy", sa.Boolean(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("symptoms_json", sa.Text(), nullable=False),
        sa.Column("actions_json", sa.Text(), nullable=False),
        sa.Column("prevention_json", sa.Text(), nullable=False),
        sa.Column("disclaimer", sa.Text(), nullable=False),
    )
    op.create_index("ix_disease_knowledge_class_id", "disease_knowledge", ["class_id"])


def downgrade() -> None:
    op.drop_table("disease_knowledge")
    op.drop_table("predictions_yield")
    op.drop_table("predictions_disease")
    op.drop_table("farms")
    op.drop_table("users")
