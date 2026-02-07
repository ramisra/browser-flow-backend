#!/usr/bin/env python3
"""Check database state and Alembic version."""

import sys
from sqlalchemy import create_engine, text
from app.core.config import settings

def main():
    print("=" * 60)
    print("Database State Check")
    print("=" * 60)
    
    db_url = settings.database_url_sync
    print(f"\nConnecting to: {db_url.split('@')[1] if '@' in db_url else 'database'}")
    
    try:
        engine = create_engine(db_url, poolclass=None)
        
        with engine.connect() as conn:
            # Check alembic_version table
            print("\n1. Checking alembic_version table...")
            try:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                version = result.fetchone()
                if version:
                    print(f"   ✓ Current version: {version[0]}")
                else:
                    print("   ⚠ Table exists but is EMPTY")
            except Exception as e:
                print(f"   ✗ Table does not exist: {e}")
            
            # Check all tables
            print("\n2. Checking all tables in public schema...")
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name NOT LIKE 'pg_%'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            if tables:
                print(f"   Found {len(tables)} table(s):")
                for table in tables:
                    print(f"     - {table}")
            else:
                print("   ✗ No tables found")
            
            # Check expected tables
            print("\n3. Checking expected tables...")
            expected = ['user_contexts', 'user_tasks', 'alembic_version']
            for table in expected:
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = :table_name
                    )
                """), {"table_name": table})
                exists = result.fetchone()[0]
                status = "✓" if exists else "✗"
                print(f"   {status} {table}")
            
            # Check if tables have data
            if 'user_contexts' in tables:
                result = conn.execute(text("SELECT COUNT(*) FROM user_contexts"))
                count = result.fetchone()[0]
                print(f"\n   user_contexts row count: {count}")
            
            if 'user_tasks' in tables:
                result = conn.execute(text("SELECT COUNT(*) FROM user_tasks"))
                count = result.fetchone()[0]
                print(f"   user_tasks row count: {count}")
            
            conn.commit()
        
        print("\n" + "=" * 60)
        print("Check complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
