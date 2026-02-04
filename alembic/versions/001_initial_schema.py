"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension (if available)
    # Note: pgvector must be installed in PostgreSQL first
    # For macOS: brew install pgvector
    # For other systems: follow pgvector installation instructions
    from sqlalchemy import text
    
    # Check if vector extension exists and create it if available
    # Use op.execute() instead of direct connection operations to work within Alembic's transaction
    try:
        op.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    except Exception as e:
        print(f"Warning: Could not create vector extension: {e}")
        print("Please install pgvector extension in PostgreSQL to use vector features.")
        print("Migration will continue without vector support.")
    
    # Create user_contexts table
    op.create_table(
        'user_contexts',
        sa.Column('context_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('context_tags', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('raw_content', sa.Text(), nullable=False),
        sa.Column('user_defined_context', sa.Text(), nullable=True),
        sa.Column('embedding', postgresql.BYTEA, nullable=True),  # Using BYTEA as fallback - can be changed to Vector(1536) when pgvector is installed
        sa.Column('url', sa.String(), nullable=True),
        sa.Column('context_type', sa.Enum('IMAGE', 'TEXT', 'VIDEO', name='contexttype'), nullable=False, server_default='TEXT'),
        sa.Column('user_guest_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('parent_topic', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['parent_topic'], ['user_contexts.context_id'], ondelete='SET NULL'),
    )
    
    # Create indexes for user_contexts
    op.create_index('ix_user_contexts_context_id', 'user_contexts', ['context_id'])
    op.create_index('ix_user_contexts_user_guest_id', 'user_contexts', ['user_guest_id'])
    op.create_index('ix_user_contexts_context_tags', 'user_contexts', ['context_tags'], postgresql_using='gin')
    # Only create vector index if vector extension is available
    # For now, skip the vector index - it can be added later when pgvector is installed
    # op.create_index('ix_user_contexts_embedding', 'user_contexts', ['embedding'], postgresql_using='ivfflat', postgresql_ops={'embedding': 'vector_cosine_ops'})
    
    # Create user_tasks table
    op.create_table(
        'user_tasks',
        sa.Column('task_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('task_type', sa.Enum('NOTE_TAKING', 'ADD_TO_KNOWLEDGE_BASE', 'QUESTION_ANSWER', 'CREATE_TODO', 'CREATE_DIAGRAMS', 'ADD_TO_GOOGLE_SHEETS', 'CREATE_LOCATION_MAP', 'COMPARE_SHOPPING_PRICES', 'CREATE_ACTION_FROM_CONTEXT', 'ADD_TO_CONTEXT', name='tasktype'), nullable=False),
        sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('user_guest_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_contexts', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default='{}'),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create indexes for user_tasks
    op.create_index('ix_user_tasks_task_id', 'user_tasks', ['task_id'])
    op.create_index('ix_user_tasks_task_type', 'user_tasks', ['task_type'])
    op.create_index('ix_user_tasks_user_guest_id', 'user_tasks', ['user_guest_id'])
    op.create_index('ix_user_tasks_user_contexts', 'user_tasks', ['user_contexts'], postgresql_using='gin')


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_user_tasks_user_contexts', table_name='user_tasks')
    op.drop_index('ix_user_tasks_user_guest_id', table_name='user_tasks')
    op.drop_index('ix_user_tasks_task_type', table_name='user_tasks')
    op.drop_index('ix_user_tasks_task_id', table_name='user_tasks')
    op.drop_index('ix_user_contexts_embedding', table_name='user_contexts')
    op.drop_index('ix_user_contexts_context_tags', table_name='user_contexts')
    op.drop_index('ix_user_contexts_user_guest_id', table_name='user_contexts')
    op.drop_index('ix_user_contexts_context_id', table_name='user_contexts')
    
    # Drop tables
    op.drop_table('user_tasks')
    op.drop_table('user_contexts')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS tasktype')
    op.execute('DROP TYPE IF EXISTS contexttype')
    
    # Drop extension (optional - comment out if you want to keep it)
    # op.execute('DROP EXTENSION IF EXISTS vector')
