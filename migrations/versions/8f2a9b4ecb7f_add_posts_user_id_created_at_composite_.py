"""add posts user_id created_at composite index for performance

Revision ID: 8f2a9b4ecb7f
Revises: 9eea3f179faa
Create Date: 2025-09-20 21:47:31.617033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f2a9b4ecb7f'
down_revision: Union[str, Sequence[str], None] = '9eea3f179faa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
