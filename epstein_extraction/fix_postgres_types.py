"""Fix PostgreSQL type mismatches for Entity Framework compatibility."""
import psycopg2

PG_CONN = {
    'host': 'localhost',
    'database': 'epstein_documents',
    'user': 'epstein_user',
    'password': 'epstein_secure_pw_2024'
}

def main():
    conn = psycopg2.connect(**PG_CONN)
    conn.autocommit = True
    cur = conn.cursor()

    # Get all tables
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Found {len(tables)} tables")

    for table in tables:
        cur.execute(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s
        """, (table,))
        columns = cur.fetchall()

        for col, dtype in columns:
            try:
                # Convert timestamps to TEXT (entity uses string)
                if 'timestamp' in dtype:
                    cur.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE TEXT USING "{col}"::TEXT')
                    print(f"  {table}.{col}: timestamp -> TEXT")

                # Convert date types to TEXT
                elif dtype == 'date':
                    cur.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE TEXT USING "{col}"::TEXT')
                    print(f"  {table}.{col}: date -> TEXT")

                # Convert file_size_bytes from TEXT to BIGINT
                elif col == 'file_size_bytes' and dtype == 'text':
                    cur.execute(f"ALTER TABLE \"{table}\" ALTER COLUMN \"{col}\" TYPE BIGINT USING NULLIF(\"{col}\", '')::BIGINT")
                    print(f"  {table}.{col}: text -> BIGINT")

            except Exception as e:
                print(f"  Error {table}.{col}: {e}")

    conn.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
