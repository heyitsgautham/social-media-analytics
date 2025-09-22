"""add performance indexes

Revision ID: 96712afada05
Revises: 8f2a9b4ecb7f
Create Date: 2025-09-20 23:02:20.522433

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96712afada05'
down_revision: Union[str, Sequence[str], None] = '8f2a9b4ecb7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add composite index for posts(user_id, created_at) for timeline queries
    # Check if index exists before creating
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'idx_posts_user_created'
    """))
    
    if not result.fetchone():
        op.create_index(
            'idx_posts_user_created',
            'posts',
            ['user_id', 'created_at'],
            unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the composite index
    op.drop_index('idx_posts_user_created', table_name='posts')
