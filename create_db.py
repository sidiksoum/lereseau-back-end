import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

try:
    conn = psycopg2.connect("postgresql://postgres:soum@localhost:5432/postgres")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'lereseaubase'")
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("CREATE DATABASE lereseaubase")
        print("Database lereseaubase created.")
    else:
        print("Database lereseaubase already exists.")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Failed to check/create db: {e}")
