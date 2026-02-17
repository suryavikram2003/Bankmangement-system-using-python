# Modified db_connection.py for PostgreSQL
import psycopg2
from psycopg2 import Error
from psycopg2.extras import DictCursor
import os

def get_db_connection():
    """
    Create and return a PostgreSQL database connection.
    Uses Render/PostgreSQL environment variables automatically.
    """
    try:
        connection = psycopg2.connect(
            host=os.environ.get('PGHOST', 'localhost'),
            port=int(os.environ.get('PGPORT', 5432)),
            user=os.environ.get('PGUSER', 'postgres'),
            password=os.environ.get('PGPASSWORD', ''),
            database=os.environ.get('PGDATABASE', 'bankdb')
        )
        return connection
    except Error as e:
        print(f"❌ Database connection error: {e}")
        return None

# Helper to get cursor with dictionary results
def get_dict_cursor(connection):
    return connection.cursor(cursor_factory=DictCursor)
