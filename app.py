from flask import Flask, render_template, request, redirect, url_for, session, flash
from db_connection import get_db_connection, get_dict_cursor
from init_db import init_database
import hashlib
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key-change-in-production')

# ──────────────────────────────────────────
# Initialize database tables on startup
# ──────────────────────────────────────────
with app.app_context():
    init_database()

# ──────────────────────────────────────────
# Utility Functions
# ──────────────────────────────────────────

def hash_password(password):
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(f):
    """Decorator to protect routes that require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to protect admin-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'Admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_account_balance(connection, account_number):
    """Fetch current balance for an account."""
    cursor = get_dict_cursor(connection)
    cursor.execute("SELECT balance FROM customers WHERE account_number = %s", (account_number,))
    result = cursor.fetchone()
    return result['balance'] if result else None


def record_transaction(cursor, account_number, txn_type, amount, balance_after, related_account, description):
    """Insert a transaction record."""
    query = """INSERT INTO transactions
               (account_number, transaction_type, amount, balance_after, related_account, description)
               VALUES (%s, %s, %s, %s, %s, %s)"""
    cursor.execute(query, (account_number, txn_type, amount, balance_after, related_account, description))


# ──────────────────────────────────────────
# Authentication Routes
# ──────────────────────────────────────────

@app.route('/')
def home():
    if 'user_id' in session:
        if session['role'] == 'Admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])

        conn = get_db_connection()
        if conn:
            cursor = get_dict_cursor(conn)
            cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s",
                           (username, password))
            user = cursor.fetchone()
            conn.close()

            if user:
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['account_number'] = user['account_number']
                flash(f'Welcome back, {username}!', 'success')

                if user['role'] == 'Admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password.', 'danger')
        else:
            flash('Database connection error. Please try again.', 'danger')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        dob = request.form['dob']
        account_type = request.form['account_type']
        initial_deposit = float(request.form['initial_deposit'])
        username = request.form['username']
        password = hash_password(request.form['password'])

        if initial_deposit < 500:
            flash('Minimum initial deposit is ₹500.', 'danger')
            return render_template('register.html')

        conn = get_db_connection()
        if conn:
            # In register route – replace this block:
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO customers
                    (name, email, phone, address, dob, account_type, balance)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING account_number
                    """, (name, email, phone, address, dob, account_type, initial_deposit))
                account_number = cursor.fetchone()[0]           # ← this gets the real new ID

    # Now record transaction with correct account_number
                record_transaction(cursor, account_number, 'Deposit', initial_deposit,
                                   initial_deposit, None, 'Initial deposit at account opening')

                cursor.execute("""INSERT INTO users (username, password, role, account_number)
                    VALUES (%s, %s, 'Customer', %s)""",
                               (username, password, account_number))

                conn.commit()
                flash(f'Account created! Your Account Number is {account_number}. Please login.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                conn.rollback()
                flash(f'Registration failed: {str(e)}', 'danger')
            finally:
                conn.close()

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ──────────────────────────────────────────
# Customer Dashboard
# ──────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    if conn:
        cursor = get_dict_cursor(conn)
        cursor.execute("SELECT * FROM customers WHERE account_number = %s",
                       (session['account_number'],))
        account = cursor.fetchone()

        cursor.execute("""SELECT * FROM transactions
                          WHERE account_number = %s
                          ORDER BY transaction_date DESC LIMIT 5""",
                       (session['account_number'],))
        recent_txns = cursor.fetchall()

        conn.close()
        return render_template('dashboard.html', account=account, transactions=recent_txns)

    flash('Database connection error.', 'danger')
    return redirect(url_for('login'))


# ──────────────────────────────────────────
# Deposit
# ──────────────────────────────────────────

@app.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        description = request.form.get('description', 'Cash deposit')

        if amount <= 0:
            flash('Deposit amount must be positive.', 'danger')
            return render_template('deposit.html')

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                acc_no = session['account_number']
                cursor.execute("UPDATE customers SET balance = balance + %s WHERE account_number = %s",
                               (amount, acc_no))
                new_balance = get_account_balance(conn, acc_no)
                record_transaction(cursor, acc_no, 'Deposit', amount,
                                   new_balance, None, description)
                conn.commit()
                flash(f'₹{amount:,.2f} deposited successfully! New balance: ₹{new_balance:,.2f}', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                conn.rollback()
                flash(f'Deposit failed: {str(e)}', 'danger')
            finally:
                conn.close()

    return render_template('deposit.html')


# ──────────────────────────────────────────
# Withdrawal
# ──────────────────────────────────────────

@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    conn = get_db_connection()
    current_balance = get_account_balance(conn, session['account_number']) if conn else 0
    if conn:
        conn.close()

    if request.method == 'POST':
        amount = float(request.form['amount'])
        description = request.form.get('description', 'Cash withdrawal')

        if amount <= 0:
            flash('Withdrawal amount must be positive.', 'danger')
            return render_template('withdraw.html', balance=current_balance)

        if amount > current_balance:
            flash(f'Insufficient funds! Available balance: ₹{current_balance:,.2f}', 'danger')
            return render_template('withdraw.html', balance=current_balance)

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                acc_no = session['account_number']
                cursor.execute("UPDATE customers SET balance = balance - %s WHERE account_number = %s",
                               (amount, acc_no))
                new_balance = get_account_balance(conn, acc_no)
                record_transaction(cursor, acc_no, 'Withdrawal', amount,
                                   new_balance, None, description)
                conn.commit()
                flash(f'₹{amount:,.2f} withdrawn successfully! Remaining balance: ₹{new_balance:,.2f}', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                conn.rollback()
                flash(f'Withdrawal failed: {str(e)}', 'danger')
            finally:
                conn.close()

    return render_template('withdraw.html', balance=current_balance)


# ──────────────────────────────────────────
# Fund Transfer
# ──────────────────────────────────────────

@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    conn = get_db_connection()
    current_balance = get_account_balance(conn, session['account_number']) if conn else 0
    if conn:
        conn.close()

    if request.method == 'POST':
        target_account = int(request.form['target_account'])
        amount = float(request.form['amount'])
        description = request.form.get('description', '')

        sender_acc = session['account_number']

        if target_account == sender_acc:
            flash('You cannot transfer to your own account.', 'danger')
            return render_template('transfer.html', balance=current_balance)

        if amount <= 0:
            flash('Transfer amount must be positive.', 'danger')
            return render_template('transfer.html', balance=current_balance)

        if amount > current_balance:
            flash(f'Insufficient funds! Available balance: ₹{current_balance:,.2f}', 'danger')
            return render_template('transfer.html', balance=current_balance)

        conn = get_db_connection()
        if conn:
            try:
                cursor = get_dict_cursor(conn)

                # Verify recipient exists
                cursor.execute("SELECT account_number, name FROM customers WHERE account_number = %s",
                               (target_account,))
                recipient = cursor.fetchone()

                if not recipient:
                    flash('Recipient account not found. Please check the account number.', 'danger')
                    conn.close()
                    return render_template('transfer.html', balance=current_balance)

                # STEP 1: WITHDRAW from sender
                cursor.execute("UPDATE customers SET balance = balance - %s WHERE account_number = %s",
                               (amount, sender_acc))
                sender_new_balance = get_account_balance(conn, sender_acc)

                sender_desc = f"Fund transfer to {recipient['name']} (A/C: {target_account})"
                if description:
                    sender_desc += f" - {description}"

                record_transaction(cursor, sender_acc, 'Transfer Sent', amount,
                                   sender_new_balance, target_account, sender_desc)

                # STEP 2: DEPOSIT into receiver
                cursor.execute("UPDATE customers SET balance = balance + %s WHERE account_number = %s",
                               (amount, target_account))
                receiver_new_balance = get_account_balance(conn, target_account)

                cursor.execute("SELECT name FROM customers WHERE account_number = %s", (sender_acc,))
                sender_info = cursor.fetchone()

                receiver_desc = f"Fund transfer from {sender_info['name']} (A/C: {sender_acc})"
                if description:
                    receiver_desc += f" - {description}"

                record_transaction(cursor, target_account, 'Transfer Received', amount,
                                   receiver_new_balance, sender_acc, receiver_desc)

                conn.commit()
                flash(f'₹{amount:,.2f} transferred successfully to {recipient["name"]} (A/C: {target_account})! '
                      f'Your new balance: ₹{sender_new_balance:,.2f}', 'success')
                return redirect(url_for('dashboard'))

            except Exception as e:
                conn.rollback()
                flash(f'Transfer failed: {str(e)}', 'danger')
            finally:
                conn.close()

    return render_template('transfer.html', balance=current_balance)


# ──────────────────────────────────────────
# Transaction History
# ──────────────────────────────────────────

@app.route('/transactions')
@login_required
def transactions():
    conn = get_db_connection()
    if conn:
        cursor = get_dict_cursor(conn)
        cursor.execute("""SELECT * FROM transactions
                          WHERE account_number = %s
                          ORDER BY transaction_date DESC""",
                       (session['account_number'],))
        all_txns = cursor.fetchall()
        conn.close()
        return render_template('transactions.html', transactions=all_txns)
    flash('Database connection error.', 'danger')
    return redirect(url_for('dashboard'))


# ──────────────────────────────────────────
# Profile
# ──────────────────────────────────────────

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db_connection()
    if request.method == 'POST':
        phone = request.form['phone']
        address = request.form['address']
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE customers SET phone = %s, address = %s WHERE account_number = %s",
                               (phone, address, session['account_number']))
                conn.commit()
                flash('Profile updated successfully!', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'Update failed: {str(e)}', 'danger')

    if conn:
        cursor = get_dict_cursor(conn)
        cursor.execute("SELECT * FROM customers WHERE account_number = %s",
                       (session['account_number'],))
        account = cursor.fetchone()
        conn.close()
        return render_template('profile.html', account=account)

    flash('Database connection error.', 'danger')
    return redirect(url_for('dashboard'))


# ──────────────────────────────────────────
# Admin Routes
# ──────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    if conn:
        cursor = get_dict_cursor(conn)

        cursor.execute("SELECT COUNT(*) as total FROM customers")
        total_accounts = cursor.fetchone()['total']

        cursor.execute("SELECT COALESCE(SUM(balance), 0) as total FROM customers")
        total_balance = cursor.fetchone()['total']

        # PostgreSQL version of today's transactions count
        cursor.execute("""
            SELECT COUNT(*) as total 
            FROM transactions 
            WHERE transaction_date::date = CURRENT_DATE
        """)
        today_txns = cursor.fetchone()['total']

        cursor.execute("""SELECT t.*, c.name FROM transactions t
                          JOIN customers c ON t.account_number = c.account_number
                          ORDER BY transaction_date DESC LIMIT 10""")
        recent_txns = cursor.fetchall()

        conn.close()
        return render_template('admin_dashboard.html',
                               total_accounts=total_accounts,
                               total_balance=total_balance,
                               today_txns=today_txns,
                               recent_txns=recent_txns)

    flash('Database connection error.', 'danger')
    return redirect(url_for('login'))


@app.route('/admin/accounts')
@admin_required
def admin_accounts():
    conn = get_db_connection()
    if conn:
        cursor = get_dict_cursor(conn)
        cursor.execute("SELECT * FROM customers ORDER BY account_number")
        accounts = cursor.fetchall()
        conn.close()
        return render_template('admin_accounts.html', accounts=accounts)

    flash('Database connection error.', 'danger')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/account/<int:acc_no>/transactions')
@admin_required
def admin_account_transactions(acc_no):
    conn = get_db_connection()
    if conn:
        cursor = get_dict_cursor(conn)

        cursor.execute("SELECT * FROM customers WHERE account_number = %s", (acc_no,))
        account = cursor.fetchone()

        cursor.execute("""SELECT * FROM transactions WHERE account_number = %s
                          ORDER BY transaction_date DESC""", (acc_no,))
        txns = cursor.fetchall()

        conn.close()
        return render_template('transactions.html', transactions=txns, account=account, admin_view=True)

    flash('Database connection error.', 'danger')
    return redirect(url_for('admin_dashboard'))


# ──────────────────────────────────────────
# Run Application
# ──────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
