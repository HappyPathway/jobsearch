"""Migration script for updating job search database schema."""
import os
from datetime import datetime
import sqlalchemy as sa
from alembic import op
import sqlalchemy

# revision identifiers, used by Alembic.
revision = '2024_04_26_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Upgrade database schema for new job search implementation."""
    # Add new columns to job_cache
    with op.batch_alter_table('job_cache') as batch_op:
        batch_op.add_column(sa.Column('first_seen_date', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('last_seen_date', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('location_type', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('company_overview', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('reasoning', sa.String(), nullable=True))
        
        # Create indexes
        batch_op.create_index('ix_job_cache_url', ['url'], unique=True)
        batch_op.create_index('ix_job_cache_company', ['company'], unique=False)
    
    # Initialize new fields with defaults
    conn = op.get_bind()
    now = datetime.now().isoformat()
    
    conn.execute(sa.text("""
        UPDATE job_cache 
        SET first_seen_date = :now,
            last_seen_date = :now,
            location_type = 'unknown',
            company_overview = '{}',
            reasoning = 'Migrated from previous version'
        WHERE first_seen_date IS NULL
    """), {"now": now})


def downgrade():
    """Revert schema changes."""
    with op.batch_alter_table('job_cache') as batch_op:
        batch_op.drop_column('first_seen_date')
        batch_op.drop_column('last_seen_date')
        batch_op.drop_column('location_type')
        batch_op.drop_column('company_overview')
        batch_op.drop_column('reasoning')
        
        batch_op.drop_index('ix_job_cache_url')
        batch_op.drop_index('ix_job_cache_company')
