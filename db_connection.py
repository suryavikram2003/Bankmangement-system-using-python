import mysql.connector
from mysql.connector import Error
import os


def get_db_connection():
    """
    Create and return a MySQL database connection.
    Uses Railway environment variables automatically.
    """
    try:
        connection = mysql.connector.connect(
            host=os.environ.get('MYSQLHOST', 'localhost'),
            port=int(os.environ.get('MYSQLPORT', 3306)),
            user=os.environ.get('MYSQLUSER', 'root'),
            password=os.environ.get('MYSQLPASSWORD', 'tiger'),
            database=os.environ.get('MYSQLDATABASE', 'railway')
        )
        return connection
    except Error as e:
        print(f"❌ Database connection error: {e}")
        return None
