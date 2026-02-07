"""Add EXTRACT_DATA_TO_SHEET and EXTRACT_DATA_TABLE to tasktype enum

Revision ID: 006_add_extract_data_types
Revises: 005_drop_intent_add_metadata
Create Date: 2026-02-05 12:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "006_add_extract_data_types"
down_revision: Union[str, None] = "005_drop_intent_add_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add EXTRACT_DATA_TO_SHEET and EXTRACT_DATA_TABLE to tasktype enum."""
    # Note: ALTER TYPE ... ADD VALUE cannot be executed inside a transaction block
    # in PostgreSQL versions < 12. For PostgreSQL 12+, this works fine.
    # If you're using PostgreSQL < 12, you may need to run these commands manually
    # outside of a transaction.
    
    # Check if the enum values already exist before adding them
    connection = op.get_bind()
    
    # Check if EXTRACT_DATA_TO_SHEET exists
    check_sheet = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumlabel = 'EXTRACT_DATA_TO_SHEET' 
            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'tasktype')
        )
    """))
    if not check_sheet.fetchone()[0]:
        try:
            op.execute(text("ALTER TYPE tasktype ADD VALUE 'EXTRACT_DATA_TO_SHEET'"))
        except Exception as e:
            # If it already exists (race condition), that's fine
            if 'already exists' not in str(e).lower():
                raise
    
    # Check if EXTRACT_DATA_TABLE exists
    check_table = connection.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_enum 
            WHERE enumlabel = 'EXTRACT_DATA_TABLE' 
            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'tasktype')
        )
    """))
    if not check_table.fetchone()[0]:
        try:
            op.execute(text("ALTER TYPE tasktype ADD VALUE 'EXTRACT_DATA_TABLE'"))
        except Exception as e:
            # If it already exists (race condition), that's fine
            if 'already exists' not in str(e).lower():
                raise


def downgrade() -> None:
    """Remove EXTRACT_DATA_TO_SHEET and EXTRACT_DATA_TABLE from tasktype enum."""
    # Note: PostgreSQL does not support removing enum values directly.
    # To properly downgrade, you would need to:
    # 1. Create a new enum without these values
    # 2. Alter the column to use the new enum
    # 3. Drop the old enum
    # 4. Rename the new enum to the old name
    # 
    # This is complex and risky if there's existing data using these values.
    # For now, we'll leave a comment indicating manual intervention is needed.
    
    # WARNING: Cannot automatically remove enum values in PostgreSQL.
    # If you need to downgrade, you must manually:
    # 1. Ensure no rows use 'EXTRACT_DATA_TO_SHEET' or 'EXTRACT_DATA_TABLE'
    # 2. Create a new enum type without these values
    # 3. Migrate the column to the new enum type
    # 4. Drop the old enum and rename the new one
    
    pass
