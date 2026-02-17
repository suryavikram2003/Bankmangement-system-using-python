# Modified init_db.py for PostgreSQL
"""
Database initialization script.
Creates all tables and default admin user on first run.
Run automatically when the app starts.
"""

from db_connection import get_db_connection, get_dict_cursor
import hashlib


def init_database():
    """Create all required tables if they don't exist."""
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot initialize database — connection failed.")
        return False

    cursor = conn.cursor()

    try:
        # ── Create customers table ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                account_number SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                phone VARCHAR(15),
                address VARCHAR(255),
                dob DATE,
                account_type TEXT DEFAULT 'Savings' CHECK (account_type IN ('Savings', 'Current')),
                balance NUMERIC(15, 2) DEFAULT 0.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── Create transactions table ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id SERIAL PRIMARY KEY,
                account_number INT NOT NULL,
                transaction_type TEXT NOT NULL CHECK (transaction_type IN ('Deposit', 'Withdrawal', 'Transfer Sent', 'Transfer Received')),
                amount NUMERIC(15, 2) NOT NULL,
                balance_after NUMERIC(15, 2) NOT NULL,
                related_account INT DEFAULT NULL,
                description VARCHAR(255),
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_number) REFERENCES customers(account_number) ON DELETE CASCADE
            )
        """)

        # ── Create users table ──
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role TEXT DEFAULT 'Customer' CHECK (role IN ('Admin', 'Customer')),
                account_number INT,
                FOREIGN KEY (account_number) REFERENCES customers(account_number) ON DELETE CASCADE
            )
        """)

        # ── Create default admin user ──
        admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
        dict_cursor = get_dict_cursor(conn)
        dict_cursor.execute("SELECT * FROM users WHERE username = 'admin'")
        if not dict_cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (username, password, role, account_number) VALUES (%s, %s, 'Admin', NULL)",
                ('admin', admin_password)
            )
            print("✅ Default admin created (username: admin, password: admin123)")

        conn.commit()
        print("✅ Database tables initialized successfully!")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Database initialization error: {e}")
        return False

    finally:
        conn.close()


if __name__ == '__main__':
    init_database()
