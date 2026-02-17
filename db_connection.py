# db_connection.py (replace your get_db_connection with this)
import os
import psycopg2
from urllib.parse import urlparse
from psycopg2 import Error
from psycopg2.extras import DictCursor

def get_db_connection():
    try:
        # 1. Prefer DATABASE_URL (Render internal style)
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            parsed = urlparse(db_url)
            return psycopg2.connect(
                database=parsed.path.lstrip('/'),
                user=parsed.username,
                password=parsed.password,
                host=parsed.hostname,
                port=parsed.port or 5432
            )

        # 2. Fallback to individual variables (your old style)
        return psycopg2.connect(
            host=os.environ.get('PGHOST'),
            port=int(os.environ.get('PGPORT', 5432)),
            database=os.environ.get('PGDATABASE'),
            user=os.environ.get('PGUSER'),
            password=os.environ.get('PGPASSWORD')
        )
    except Error as e:
        print(f"❌ Database connection error: {e}")
        return None

def get_dict_cursor(connection):
    return connection.cursor(cursor_factory=DictCursor)
