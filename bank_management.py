import psycopg2
from psycopg2 import Error
from psycopg2.extras import DictCursor
from datetime import date
import hashlib
import sys
import os
# ──────────────────────────────────────────
# Database Helpers (you can move these to db_connection.py later)
# ──────────────────────────────────────────

def create_connection():
    """Create PostgreSQL connection using environment variables (Render-friendly)"""
    try:
        conn = psycopg2.connect(
            host=os.environ.get('PGHOST', 'localhost'),
            port=int(os.environ.get('PGPORT', '5432')),
            database=os.environ.get('PGDATABASE', 'bankdb'),
            user=os.environ.get('PGUSER', 'postgres'),
            password=os.environ.get('PGPASSWORD', '')
        )
        conn.autocommit = False   # Important: we want manual commit/rollback
        print("✅ Successfully connected to PostgreSQL database")
        return conn
    except Error as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        return None


def close_connection(connection):
    if connection and not connection.closed:
        connection.close()
        print("Database connection closed.")


def get_dict_cursor(connection):
    return connection.cursor(cursor_factory=DictCursor)


# ──────────────────────────────────────────
# Utility Functions
# ──────────────────────────────────────────

def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def display_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 55)
    print(f"  {title}")
    print("=" * 55)


# ──────────────────────────────────────────
# Account Operations
# ──────────────────────────────────────────

def create_account(connection):
    """Create a new bank account."""
    display_header("CREATE NEW ACCOUNT")
    try:
        name = input("  Full Name       : ")
        email = input("  Email           : ")
        phone = input("  Phone Number    : ")
        address = input("  Address         : ")
        dob = input("  Date of Birth (YYYY-MM-DD): ")
        acc_type = input("  Account Type (Savings/Current): ").capitalize()
        initial_deposit = float(input("  Initial Deposit : ₹"))

        if acc_type not in ('Savings', 'Current'):
            print("  ❌ Invalid account type. Choose 'Savings' or 'Current'.")
            return

        if initial_deposit < 500:
            print("  ❌ Minimum initial deposit is ₹500.")
            return

        cursor = connection.cursor()

        # Insert customer
        query = """INSERT INTO customers 
                   (name, email, phone, address, dob, account_type, balance) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING account_number"""
        values = (name, email, phone, address, dob, acc_type, initial_deposit)
        cursor.execute(query, values)
        account_number = cursor.fetchone()[0]

        # Record the initial deposit as a transaction
        txn_query = """INSERT INTO transactions 
                       (account_number, transaction_type, amount, balance_after, description)
                       VALUES (%s, 'Deposit', %s, %s, 'Initial deposit')"""
        cursor.execute(txn_query, (account_number, initial_deposit, initial_deposit))

        # Create login credentials
        username = input("  Choose a Username: ")
        password = hash_password(input("  Choose a Password: "))

        user_query = """INSERT INTO users (username, password, role, account_number) 
                        VALUES (%s, %s, 'Customer', %s)"""
        cursor.execute(user_query, (username, password, account_number))

        connection.commit()
        print(f"\n  ✅ Account created successfully!")
        print(f"  🔢 Your Account Number: {account_number}")

    except Error as e:
        connection.rollback()
        print(f"  ❌ Error: {e}")


def view_account(connection, account_number):
    """Display account details."""
    display_header("ACCOUNT DETAILS")
    try:
        cursor = get_dict_cursor(connection)
        query = "SELECT * FROM customers WHERE account_number = %s"
        cursor.execute(query, (account_number,))
        account = cursor.fetchone()
        if account:
            print(f" Account Number : {account['account_number']}")
            print(f" Name           : {account['name']}")
            print(f" Email          : {account['email']}")
            print(f" Phone          : {account['phone']}")
            print(f" Address        : {account['address']}")
            print(f" Date of Birth  : {account['dob']}")
            print(f" Account Type   : {account['account_type']}")
            print(f" Balance        : ₹{account['balance']:,.2f}")
            print(f" Opened On      : {account['created_at']}")
        else:
            print(" ❌ Account not found.")
    except Error as e:
        print(f" ❌ Error: {e}")


def update_account(connection, account_number):
    """Update customer details."""
    display_header("UPDATE ACCOUNT DETAILS")
    try:
        print(" Leave blank to keep current value.\n")
        name = input(" New Name    : ")
        email = input(" New Email   : ")
        phone = input(" New Phone   : ")
        address = input(" New Address : ")

        cursor = connection.cursor()
        updates = []
        values = []
        if name:
            updates.append("name = %s")
            values.append(name)
        if email:
            updates.append("email = %s")
            values.append(email)
        if phone:
            updates.append("phone = %s")
            values.append(phone)
        if address:
            updates.append("address = %s")
            values.append(address)

        if not updates:
            print(" ℹ️ No changes made.")
            return

        values.append(account_number)
        query = f"UPDATE customers SET {', '.join(updates)} WHERE account_number = %s"
        cursor.execute(query, tuple(values))
        connection.commit()
        print(" ✅ Account updated successfully!")
    except Error as e:
        connection.rollback()
        print(f" ❌ Error: {e}")


def delete_account(connection, account_number):
    """Delete a bank account."""
    display_header("DELETE ACCOUNT")
    confirm = input(f" ⚠️ Delete account {account_number}? (yes/no): ").lower()
    if confirm == 'yes':
        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM customers WHERE account_number = %s", (account_number,))
            connection.commit()
            print(" ✅ Account deleted successfully.")
        except Error as e:
            connection.rollback()
            print(f" ❌ Error: {e}")
    else:
        print(" ℹ️ Deletion cancelled.")


# ──────────────────────────────────────────
# Transaction Operations
# ──────────────────────────────────────────

def deposit(connection, account_number):
    """Deposit money into an account."""
    display_header("DEPOSIT MONEY")
    try:
        amount = float(input(" Enter amount to deposit: ₹"))
        if amount <= 0:
            print(" ❌ Amount must be positive.")
            return

        cursor = connection.cursor()
        # Update balance
        cursor.execute("UPDATE customers SET balance = balance + %s WHERE account_number = %s",
                       (amount, account_number))
        # Get new balance
        cursor.execute("SELECT balance FROM customers WHERE account_number = %s", (account_number,))
        new_balance = cursor.fetchone()[0]

        # Record transaction
        txn_query = """INSERT INTO transactions
                       (account_number, transaction_type, amount, balance_after, description)
                       VALUES (%s, 'Deposit', %s, %s, %s)"""
        cursor.execute(txn_query, (account_number, amount, new_balance, "Cash deposit"))

        connection.commit()
        print(f" ✅ ₹{amount:,.2f} deposited successfully!")
        print(f" 💰 New Balance: ₹{new_balance:,.2f}")
    except Error as e:
        connection.rollback()
        print(f" ❌ Error: {e}")


def withdraw(connection, account_number):
    """Withdraw money from an account."""
    display_header("WITHDRAW MONEY")
    try:
        amount = float(input(" Enter amount to withdraw: ₹"))
        if amount <= 0:
            print(" ❌ Amount must be positive.")
            return

        cursor = connection.cursor()
        cursor.execute("SELECT balance FROM customers WHERE account_number = %s", (account_number,))
        current_balance = cursor.fetchone()[0]

        if amount > current_balance:
            print(f" ❌ Insufficient funds! Available balance: ₹{current_balance:,.2f}")
            return

        # Update balance
        cursor.execute("UPDATE customers SET balance = balance - %s WHERE account_number = %s",
                       (amount, account_number))
        new_balance = current_balance - amount

        # Record transaction
        txn_query = """INSERT INTO transactions
                       (account_number, transaction_type, amount, balance_after, description)
                       VALUES (%s, 'Withdrawal', %s, %s, %s)"""
        cursor.execute(txn_query, (account_number, amount, new_balance, "Cash withdrawal"))

        connection.commit()
        print(f" ✅ ₹{amount:,.2f} withdrawn successfully!")
        print(f" 💰 Remaining Balance: ₹{new_balance:,.2f}")
    except Error as e:
        connection.rollback()
        print(f" ❌ Error: {e}")


def transfer(connection, account_number):
    """Transfer money between accounts."""
    display_header("FUND TRANSFER")
    try:
        target_acc = int(input(" Enter recipient's Account Number: "))
        amount = float(input(" Enter amount to transfer: ₹"))

        if amount <= 0:
            print(" ❌ Amount must be positive.")
            return

        cursor = connection.cursor()

        # Check sender balance
        cursor.execute("SELECT balance FROM customers WHERE account_number = %s", (account_number,))
        sender_balance = cursor.fetchone()[0]

        if amount > sender_balance:
            print(f" ❌ Insufficient funds! Available: ₹{sender_balance:,.2f}")
            return

        # Check if target account exists
        cursor.execute("SELECT name FROM customers WHERE account_number = %s", (target_acc,))
        recipient = cursor.fetchone()
        if not recipient:
            print(" ❌ Recipient account not found.")
            return

        # Debit sender
        cursor.execute("UPDATE customers SET balance = balance - %s WHERE account_number = %s",
                       (amount, account_number))

        # Credit receiver
        cursor.execute("UPDATE customers SET balance = balance + %s WHERE account_number = %s",
                       (amount, target_acc))

        # Get updated balances
        cursor.execute("SELECT balance FROM customers WHERE account_number = %s", (account_number,))
        sender_new = cursor.fetchone()[0]
        cursor.execute("SELECT balance FROM customers WHERE account_number = %s", (target_acc,))
        receiver_new = cursor.fetchone()[0]

        # Record transactions for both parties
        txn_query = """INSERT INTO transactions
                       (account_number, transaction_type, amount, balance_after, description)
                       VALUES (%s, 'Transfer Sent', %s, %s, %s)"""
        cursor.execute(txn_query, (account_number, amount, sender_new,
                                   f"Transfer to A/C {target_acc}"))

        txn_query_received = """INSERT INTO transactions
                                (account_number, transaction_type, amount, balance_after, description)
                                VALUES (%s, 'Transfer Received', %s, %s, %s)"""
        cursor.execute(txn_query_received, (target_acc, amount, receiver_new,
                                            f"Transfer from A/C {account_number}"))

        connection.commit()
        print(f"\n ✅ ₹{amount:,.2f} transferred to {recipient[0]} (A/C: {target_acc})")
        print(f" 💰 Your Balance: ₹{sender_new:,.2f}")

    except Error as e:
        connection.rollback()
        print(f" ❌ Error: {e}")


def view_transactions(connection, account_number):
    """View transaction history."""
    display_header("TRANSACTION HISTORY")
    try:
        cursor = get_dict_cursor(connection)
        query = """SELECT * FROM transactions
                   WHERE account_number = %s
                   ORDER BY transaction_date DESC LIMIT 20"""
        cursor.execute(query, (account_number,))
        transactions = cursor.fetchall()

        if not transactions:
            print(" ℹ️ No transactions found.")
            return

        print(f" {'ID':<6} {'Type':<15} {'Amount':>12} {'Balance':>12} {'Date':<20} {'Description'}")
        print(" " + "-" * 95)
        for txn in transactions:
            print(f" {txn['transaction_id']:<6} {txn['transaction_type']:<15} "
                  f"₹{txn['amount']:>10,.2f} ₹{txn['balance_after']:>10,.2f} "
                  f"{str(txn['transaction_date']):<20} {txn['description'] or ''}")
    except Error as e:
        print(f" ❌ Error: {e}")


def check_balance(connection, account_number):
    """Check account balance."""
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT balance FROM customers WHERE account_number = %s", (account_number,))
        balance = cursor.fetchone()
        if balance:
            print(f"\n 💰 Current Balance: ₹{balance[0]:,.2f}")
        else:
            print(" ❌ Account not found.")
    except Error as e:
        print(f" ❌ Error: {e}")


# ──────────────────────────────────────────
# Admin Operations
# ──────────────────────────────────────────

def list_all_accounts(connection):
    """List all customer accounts (Admin only)."""
    display_header("ALL CUSTOMER ACCOUNTS")
    try:
        cursor = get_dict_cursor(connection)
        cursor.execute("""SELECT account_number, name, account_type, balance, created_at 
                          FROM customers ORDER BY account_number""")
        accounts = cursor.fetchall()

        if not accounts:
            print(" ℹ️ No accounts found.")
            return

        print(f" {'A/C No.':<10} {'Name':<25} {'Type':<10} {'Balance':>15} {'Opened On'}")
        print(" " + "-" * 80)
        for acc in accounts:
            print(f" {acc['account_number']:<10} {acc['name']:<25} {acc['account_type']:<10} "
                  f"₹{acc['balance']:>13,.2f} {str(acc['created_at'])}")
    except Error as e:
        print(f" ❌ Error: {e}")


# ──────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────

def login(connection):
    """User login."""
    display_header("LOGIN")
    username = input(" Username: ")
    password = hash_password(input(" Password: "))
    try:
        cursor = get_dict_cursor(connection)
        query = "SELECT * FROM users WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()
        if user:
            print(f"\n ✅ Welcome, {username}! (Role: {user['role']})")
            return user
        else:
            print(" ❌ Invalid username or password.")
            return None
    except Error as e:
        print(f" ❌ Error: {e}")
        return None


def create_admin(connection):
    """Create a default admin account (run once)."""
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM users WHERE role = 'Admin'")
        if cursor.fetchone():
            return  # Admin already exists

        admin_pass = hash_password("admin123")
        cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', %s, 'Admin')",
                       (admin_pass,))
        connection.commit()
        print(" ℹ️ Default admin created (username: admin, password: admin123)")
    except Error as e:
        print(f" ❌ Error: {e}")


# ──────────────────────────────────────────
# Menus
# ──────────────────────────────────────────

def customer_menu(connection, user):
    """Customer menu after login."""
    account_number = user['account_number']
    while True:
        display_header("CUSTOMER MENU")
        print(" 1. View Account Details")
        print(" 2. Deposit Money")
        print(" 3. Withdraw Money")
        print(" 4. Transfer Funds")
        print(" 5. Check Balance")
        print(" 6. Transaction History")
        print(" 7. Update Account Info")
        print(" 8. Delete Account")
        print(" 9. Logout")
        print()

        choice = input(" Enter your choice (1-9): ")

        if choice == '1':
            view_account(connection, account_number)
        elif choice == '2':
            deposit(connection, account_number)
        elif choice == '3':
            withdraw(connection, account_number)
        elif choice == '4':
            transfer(connection, account_number)
        elif choice == '5':
            check_balance(connection, account_number)
        elif choice == '6':
            view_transactions(connection, account_number)
        elif choice == '7':
            update_account(connection, account_number)
        elif choice == '8':
            delete_account(connection, account_number)
            # You may want to break or re-login after delete
            break
        elif choice == '9':
            print(" 👋 Logged out successfully.")
            break
        else:
            print(" ❌ Invalid choice. Try again.")


def admin_menu(connection):
    """Admin menu after login."""
    while True:
        display_header("ADMIN MENU")
        print(" 1. View All Accounts")
        print(" 2. Search Account by Number")
        print(" 3. Create New Account")
        print(" 4. Delete Account")
        print(" 5. Logout")
        print()

        choice = input(" Enter your choice (1-5): ")

        if choice == '1':
            list_all_accounts(connection)
        elif choice == '2':
            try:
                acc_no = int(input(" Enter Account Number: "))
                view_account(connection, acc_no)
            except ValueError:
                print(" ❌ Invalid account number.")
        elif choice == '3':
            create_account(connection)
        elif choice == '4':
            try:
                acc_no = int(input(" Enter Account Number to delete: "))
                delete_account(connection, acc_no)
            except ValueError:
                print(" ❌ Invalid account number.")
        elif choice == '5':
            print(" 👋 Admin logged out.")
            break
        else:
            print(" ❌ Invalid choice.")


# ──────────────────────────────────────────
# Main Application
# ──────────────────────────────────────────

def main():
    """Main entry point."""
    connection = create_connection()
    if not connection:
        print("❌ Failed to connect to the database. Exiting.")
        sys.exit(1)

    # Create default admin if first run
    create_admin(connection)

    while True:
        display_header("🏦 BANK MANAGEMENT SYSTEM")
        print(" 1. Login")
        print(" 2. Create New Account")
        print(" 3. Exit")
        print()

        choice = input(" Enter your choice (1-3): ")

        if choice == '1':
            user = login(connection)
            if user:
                if user['role'] == 'Admin':
                    admin_menu(connection)
                else:
                    customer_menu(connection, user)

        elif choice == '2':
            create_account(connection)

        elif choice == '3':
            close_connection(connection)
            print("\n  👋 Thank you for using Bank Management System!")
            print("  Goodbye!\n")
            sys.exit(0)

        else:
            print("  ❌ Invalid choice. Try again.")


if __name__ == "__main__":
    main()
