"""
Migrate data from SQLite to PostgreSQL - Dynamic schema detection.
"""
import sqlite3
import psycopg2
from psycopg2.extras import execute_batch

# Connection settings
SQLITE_PATH = r'C:\Development\EpsteinDownloader\extraction_output\epstein_documents.db'
PG_CONN = {
    'host': 'localhost',
    'database': 'epstein_documents',
    'user': 'epstein_user',
    'password': 'epstein_secure_pw_2024'
}

# SQLite to PostgreSQL type mapping
TYPE_MAP = {
    'INTEGER': 'INTEGER',
    'TEXT': 'TEXT',
    'REAL': 'DOUBLE PRECISION',
    'BLOB': 'BYTEA',
    'NUMERIC': 'NUMERIC',
    'BOOLEAN': 'BOOLEAN',
    'DATETIME': 'TIMESTAMP',
    'DATE': 'DATE',
}

def get_sqlite_tables(sqlite_cur):
    """Get all table names from SQLite."""
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return [row[0] for row in sqlite_cur.fetchall()]

def get_table_schema(sqlite_cur, table_name):
    """Get column definitions for a table."""
    sqlite_cur.execute(f"PRAGMA table_info({table_name})")
    columns = []
    for row in sqlite_cur.fetchall():
        col_id, name, col_type, not_null, default_val, pk = row
        # Map SQLite type to PostgreSQL type
        pg_type = 'TEXT'  # Default
        col_type_upper = (col_type or 'TEXT').upper()
        for sqlite_type, postgres_type in TYPE_MAP.items():
            if sqlite_type in col_type_upper:
                pg_type = postgres_type
                break
        columns.append({
            'name': name,
            'type': pg_type,
            'not_null': not_null,
            'pk': pk,
            'default': default_val
        })
    return columns

def create_table(pg_cur, table_name, columns):
    """Create a PostgreSQL table from column definitions."""
    col_defs = []
    for col in columns:
        col_def = f'"{col["name"]}" {col["type"]}'
        if col['pk']:
            col_def += ' PRIMARY KEY'
        col_defs.append(col_def)

    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(col_defs)})'
    try:
        pg_cur.execute(create_sql)
        return True
    except Exception as e:
        print(f"    Create table error: {e}")
        return False

def convert_row(row, columns):
    """Convert a row to handle type differences between SQLite and PostgreSQL."""
    result = list(row)
    for i, col in enumerate(columns):
        if col['type'] == 'BOOLEAN' and result[i] is not None:
            # Convert SQLite integer to PostgreSQL boolean
            result[i] = bool(result[i])
    return tuple(result)

def migrate_table(sqlite_cur, pg_conn, table_name):
    """Migrate a single table from SQLite to PostgreSQL."""
    pg_cur = pg_conn.cursor()

    try:
        # Get column names
        columns = get_table_schema(sqlite_cur, table_name)
        if not columns:
            print(f"  {table_name}: skipped (no columns)")
            return 0

        # Check for multiple primary keys (composite key - not supported in simple creation)
        pk_count = sum(1 for c in columns if c['pk'])
        if pk_count > 1:
            # Handle composite primary key
            col_defs = []
            pk_cols = []
            for col in columns:
                col_def = f'"{col["name"]}" {col["type"]}'
                col_defs.append(col_def)
                if col['pk']:
                    pk_cols.append(f'"{col["name"]}"')
            col_defs.append(f'PRIMARY KEY ({", ".join(pk_cols)})')
            create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(col_defs)})'
            try:
                pg_cur.execute(create_sql)
                pg_conn.commit()
            except Exception as e:
                print(f"  {table_name}: ERROR creating table - {e}")
                pg_conn.rollback()
                return 0
        else:
            # Create table in PostgreSQL (single or no primary key)
            if not create_table(pg_cur, table_name, columns):
                pg_conn.rollback()
                return 0
            pg_conn.commit()

        col_names = [c['name'] for c in columns]

        # Read data from SQLite
        sqlite_cur.execute(f'SELECT * FROM "{table_name}"')
        rows = sqlite_cur.fetchall()

        if not rows:
            print(f"  {table_name}: 0 rows (schema created)")
            return 0

        # Convert rows to handle type differences
        converted_rows = [convert_row(row, columns) for row in rows]

        # Build insert query
        col_list = ', '.join(f'"{c}"' for c in col_names)
        placeholders = ', '.join(['%s'] * len(col_names))
        insert_sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

        # Insert in batches
        batch_size = 1000
        inserted = 0
        for i in range(0, len(converted_rows), batch_size):
            batch = converted_rows[i:i+batch_size]
            execute_batch(pg_cur, insert_sql, batch)
            inserted += len(batch)
            pg_conn.commit()

        print(f"  {table_name}: {inserted:,} rows")
        return inserted

    except Exception as e:
        print(f"  {table_name}: ERROR - {e}")
        pg_conn.rollback()
        return 0

def main():
    print("=== SQLite to PostgreSQL Migration ===\n")

    # Connect to databases
    print("Connecting to SQLite...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()

    print("Connecting to PostgreSQL...")
    pg_conn = psycopg2.connect(**PG_CONN)

    # Get all tables from SQLite
    tables = get_sqlite_tables(sqlite_cur)
    print(f"\nFound {len(tables)} tables in SQLite")

    # Migrate tables
    print("\nMigrating tables...")
    total_rows = 0
    for table in tables:
        rows = migrate_table(sqlite_cur, pg_conn, table)
        total_rows += rows

    # Close connections
    sqlite_conn.close()
    pg_conn.close()

    print(f"\n=== Migration Complete ===")
    print(f"Total rows migrated: {total_rows:,}")

if __name__ == "__main__":
    main()
