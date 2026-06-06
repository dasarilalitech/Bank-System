import os
import random
import sqlite3
from contextlib import closing
from datetime import datetime

from flask import Flask, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "banking.db")


def get_db():
    return sqlite3.connect(DB_PATH)


# ---------- DATABASE ----------
def init_db():
    with closing(get_db()) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_name TEXT NOT NULL,
            account_number TEXT UNIQUE NOT NULL,
            balance REAL DEFAULT 1000,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_account TEXT NOT NULL,
            receiver_account TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL
        )
        """)

        conn.commit()


init_db()


# ---------- HELPERS ----------
def generate_account_number(cur):
    while True:
        account_number = str(random.randint(100000, 999999))
        cur.execute(
            "SELECT id FROM accounts WHERE account_number=?",
            (account_number,)
        )
        if not cur.fetchone():
            return account_number


def login_required():
    return "user_id" in session


def clean_text(value):
    return value.strip() if value else ""


# ---------- HOME ----------
@app.route("/")
def home():
    return render_template("index.html")


# ---------- REGISTER ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = clean_text(request.form.get("username"))
        password = request.form.get("password", "")

        if not username or not password:
            return "Username and password are required"

        hashed_password = generate_password_hash(password)

        with closing(get_db()) as conn:
            cur = conn.cursor()

            try:
                cur.execute(
                    "INSERT INTO users(username, password) VALUES(?, ?)",
                    (username, hashed_password)
                )
                user_id = cur.lastrowid

                accounts = [
                    ("Savings", generate_account_number(cur), 5000),
                    ("Business", generate_account_number(cur), 10000),
                ]

                cur.executemany("""
                    INSERT INTO accounts(user_id, account_name, account_number, balance)
                    VALUES(?, ?, ?, ?)
                """, [
                    (user_id, account_name, account_number, balance)
                    for account_name, account_number, balance in accounts
                ])

                conn.commit()
            except sqlite3.IntegrityError:
                conn.rollback()
                return "User already exists"

        return redirect("/login")

    return render_template("register.html")


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = clean_text(request.form.get("username"))
        password = request.form.get("password", "")

        with closing(get_db()) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, username, password FROM users WHERE username=?",
                (username,)
            )
            user = cur.fetchone()

        if user and check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect("/dashboard")

        return "Invalid credentials"

    return render_template("login.html")


# ---------- DASHBOARD ----------
@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect("/login")

    with closing(get_db()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM accounts WHERE user_id=?",
            (session["user_id"],)
        )
        accounts = cur.fetchall()

    return render_template(
        "dashboard.html",
        username=session["username"],
        accounts=accounts
    )


# ---------- TRANSFER ----------
@app.route("/transfer", methods=["POST"])
def transfer():
    if not login_required():
        return redirect("/login")

    sender = clean_text(request.form.get("sender"))
    receiver = clean_text(request.form.get("receiver"))

    try:
        amount = float(request.form.get("amount", 0))
    except ValueError:
        return "Invalid amount"

    if amount <= 0:
        return "Amount must be greater than zero"

    if sender == receiver:
        return "Sender and receiver accounts must be different"

    with closing(get_db()) as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT balance FROM accounts
            WHERE account_number=? AND user_id=?
        """, (sender, session["user_id"]))
        sender_data = cur.fetchone()

        if not sender_data:
            return "Sender account not found"

        if sender_data[0] < amount:
            return "Insufficient balance"

        cur.execute(
            "SELECT id FROM accounts WHERE account_number=?",
            (receiver,)
        )
        receiver_data = cur.fetchone()

        if not receiver_data:
            return "Receiver account not found"

        try:
            cur.execute(
                "UPDATE accounts SET balance = balance - ? WHERE account_number=?",
                (amount, sender)
            )
            cur.execute(
                "UPDATE accounts SET balance = balance + ? WHERE account_number=?",
                (amount, receiver)
            )
            cur.execute("""
                INSERT INTO transactions(sender_account, receiver_account, amount, date)
                VALUES(?, ?, ?, ?)
            """, (
                sender,
                receiver,
                amount,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            return "Transfer failed"

    return redirect("/dashboard")


# ---------- TRANSACTIONS ----------
@app.route("/transactions")
def transactions():
    if not login_required():
        return redirect("/login")

    with closing(get_db()) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM transactions
            WHERE sender_account IN (
                SELECT account_number FROM accounts WHERE user_id=?
            )
            OR receiver_account IN (
                SELECT account_number FROM accounts WHERE user_id=?
            )
            ORDER BY id DESC
        """, (session["user_id"], session["user_id"]))
        transactions = cur.fetchall()

    return render_template(
        "transactions.html",
        transactions=transactions
    )


# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------- RUN APP ----------
if __name__ == "__main__":
    app.run(debug=True)
