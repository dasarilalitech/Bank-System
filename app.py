from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

# ---------- DATABASE ----------
def init_db():

    conn = sqlite3.connect("banking.db")
    cur = conn.cursor()

    # USERS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # ACCOUNTS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        account_name TEXT,
        account_number TEXT UNIQUE,
        balance REAL DEFAULT 1000
    )
    """)

    # TRANSACTIONS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_account TEXT,
        receiver_account TEXT,
        amount REAL,
        date TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------- GENERATE ACCOUNT NUMBER ----------
def generate_account_number():
    return str(random.randint(100000, 999999))

# ---------- HOME ----------
@app.route('/')
def home():
    return render_template("index.html")

# ---------- REGISTER ----------
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("banking.db")
        cur = conn.cursor()

        try:

            # insert user
            cur.execute("""
            INSERT INTO users(username, password)
            VALUES(?, ?)
            """, (username, password))

            user_id = cur.lastrowid

            # savings account
            cur.execute("""
            INSERT INTO accounts(
                user_id,
                account_name,
                account_number,
                balance
            )
            VALUES(?,?,?,?)
            """, (
                user_id,
                "Savings",
                generate_account_number(),
                5000
            ))

            # business account
            cur.execute("""
            INSERT INTO accounts(
                user_id,
                account_name,
                account_number,
                balance
            )
            VALUES(?,?,?,?)
            """, (
                user_id,
                "Business",
                generate_account_number(),
                10000
            ))

            conn.commit()

        except:
            return "User already exists"

        conn.close()

        return redirect('/login')

    return render_template("register.html")

# ---------- LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect("banking.db")
        cur = conn.cursor()

        cur.execute("""
        SELECT * FROM users
        WHERE username=? AND password=?
        """, (username, password))

        user = cur.fetchone()

        conn.close()

        if user:

            session['user_id'] = user[0]
            session['username'] = username

            return redirect('/dashboard')

        return "Invalid credentials"

    return render_template("login.html")

# ---------- DASHBOARD ----------
@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect("banking.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM accounts
    WHERE user_id=?
    """, (session['user_id'],))

    accounts = cur.fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        username=session['username'],
        accounts=accounts
    )

# ---------- TRANSFER ----------
@app.route('/transfer', methods=['POST'])
def transfer():

    sender = request.form['sender']
    receiver = request.form['receiver']
    amount = float(request.form['amount'])

    conn = sqlite3.connect("banking.db")
    cur = conn.cursor()

    # sender balance
    cur.execute("""
    SELECT balance FROM accounts
    WHERE account_number=?
    """, (sender,))

    sender_data = cur.fetchone()

    if not sender_data:
        conn.close()
        return "Sender account not found"

    sender_balance = sender_data[0]

    # insufficient balance
    if sender_balance < amount:
        conn.close()
        return "Insufficient balance"

    # receiver exists?
    cur.execute("""
    SELECT * FROM accounts
    WHERE account_number=?
    """, (receiver,))

    receiver_data = cur.fetchone()

    if not receiver_data:
        conn.close()
        return "Receiver account not found"

    # subtract sender
    cur.execute("""
    UPDATE accounts
    SET balance = balance - ?
    WHERE account_number=?
    """, (amount, sender))

    # add receiver
    cur.execute("""
    UPDATE accounts
    SET balance = balance + ?
    WHERE account_number=?
    """, (amount, receiver))

    # save transaction
    cur.execute("""
    INSERT INTO transactions(
        sender_account,
        receiver_account,
        amount,
        date
    )
    VALUES(?,?,?,?)
    """, (
        sender,
        receiver,
        amount,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return redirect('/dashboard')

# ---------- TRANSACTIONS ----------
@app.route('/transactions')
def transactions():

    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect("banking.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM transactions
    ORDER BY id DESC
    """)

    transactions = cur.fetchall()

    conn.close()

    return render_template(
        "transactions.html",
        transactions=transactions
    )

# ---------- LOGOUT ----------
@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

# ---------- RUN APP ----------
if __name__ == '__main__':
    app.run(debug=True)