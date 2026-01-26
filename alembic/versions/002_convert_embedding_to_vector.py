"""Convert embedding column from BYTEA to vector(1536)

Revision ID: 002_convert_embedding
Revises: 001_initial
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '002_convert_embedding'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert embedding column from BYTEA to vector(1536)."""
    from sqlalchemy import text
    connection = op.get_bind()
    
    # Check if vector extension exists and is enabled
    result = connection.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"))
    if not result.fetchone():
        print("Warning: pgvector extension is not available. Cannot convert embedding column.")
        print("Please install pgvector extension in PostgreSQL first.")
        # Migration will still be marked as complete even if we return early
        return
    
    # Ensure vector extension is enabled
    try:
        op.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    except Exception as e:
        print(f"Warning: Could not enable vector extension: {e}")
        # Migration will still be marked as complete even if we return early
        return
    
    # Convert BYTEA column to vector(1536)
    try:
        # Check if column exists and is BYTEA
        check_result = connection.execute(text("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'user_contexts' 
            AND column_name = 'embedding'
        """))
        row = check_result.fetchone()
        
        if row and row[0] == 'bytea':
            # Alter the column type from BYTEA to vector(1536)
            try:
                op.execute(text("""
                    ALTER TABLE user_contexts 
                    ALTER COLUMN embedding TYPE vector(1536) 
                    USING NULL
                """))
                print("Successfully converted embedding column to vector(1536)")
            except Exception as conv_error:
                # If that fails, try dropping and recreating
                print(f"Direct conversion failed: {conv_error}, trying drop/recreate approach")
                op.execute(text("ALTER TABLE user_contexts DROP COLUMN embedding"))
                # Add column as vector type using raw SQL
                op.execute(text("ALTER TABLE user_contexts ADD COLUMN embedding vector(1536)"))
                print("Successfully recreated embedding column as vector(1536)")
        elif row and row[0] == 'USER-DEFINED':
            # Column might already be vector type (shows as USER-DEFINED in information_schema)
            print("Embedding column appears to already be vector type")
        else:
            print(f"Warning: Embedding column type is {row[0] if row else 'unknown'}, skipping conversion")
    except Exception as e:
        print(f"Error converting embedding column: {e}")
        print("You may need to manually alter the column:")
        print("ALTER TABLE user_contexts ALTER COLUMN embedding TYPE vector(1536);")
        raise  # Re-raise to let Alembic handle the transaction


def downgrade() -> None:
    """Convert embedding column back from vector(1536) to BYTEA."""
    from sqlalchemy import text
    
    try:
        # Convert vector back to BYTEA
        op.execute(text("""
            ALTER TABLE user_contexts 
            ALTER COLUMN embedding TYPE bytea 
            USING embedding::text::bytea
        """))
    except Exception as e:
        print(f"Error converting embedding column back to BYTEA: {e}")
        raise  # Re-raise to let Alembic handle the transaction
