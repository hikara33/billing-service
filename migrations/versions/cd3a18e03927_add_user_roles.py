"""add user roles

Revision ID: cd3a18e03927
Revises: 0aa6018b77bf
Create Date: 2026-09-06 17:12:33.950683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cd3a18e03927"
down_revision: Union[str, Sequence[str], None] = "0aa6018b77bf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_role = sa.Enum(
        "ADMIN",
        "SUPPORT",
        "USER",
        name="userrole",
    )

    user_role.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "role",
            user_role,
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "role")

    user_role = sa.Enum(
        "ADMIN",
        "SUPPORT",
        "USER",
        name="userrole",
    )

    user_role.drop(op.get_bind(), checkfirst=True)