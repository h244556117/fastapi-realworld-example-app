"""add favorites_count to articles

Revision ID: 0002_add_favorites_count_to_articles
Revises: fdf8821871d7
Create Date: 2023-10-05 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0002_add_favorites_count_to_articles"
down_revision = "fdf8821871d7"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add favorites_count column to articles table
    op.add_column(
        "articles",
        sa.Column("favorites_count", sa.Integer, nullable=False, server_default="0")
    )
    
    # Update existing articles with the correct favorites_count
    op.execute("""
        UPDATE articles
        SET favorites_count = (
            SELECT COUNT(*) FROM favorites WHERE favorites.article_id = articles.id
        )
    """)

def downgrade() -> None:
    # Remove favorites_count column from articles table
    op.drop_column("articles", "favorites_count")
