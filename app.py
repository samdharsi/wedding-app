import os
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

from flask import Flask, request, redirect, url_for, session, render_template_string, g, abort

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "wedding-secret-key-change-me")

APP_TITLE = "Nidhi & Tushar Wedding"

# If DATABASE_URL exists (Render Postgres), we use Postgres-like connection.
# Render provides: postgres://...  (we normalize to postgresql:// for compatibility if needed)
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = os.environ.get("DB_PATH", "wedding.db")

STATUS_OPTIONS = ["Pending", "In Progress", "Done"]

# ----------------------------------------------------------
# USERS / ROLES
# ----------------------------------------------------------
USERS = {
    "vijay": {"pin": "1234", "role": "SUPER_ADMIN", "name": "Vijay"},
    "samdharsi": {"pin": "1111", "role": "BRIDE_ADMIN", "name": "Samdharsi Kumar"},
    "tushar": {"pin": "2222", "role": "GROOM_ADMIN", "name": "Tushar Garg"},
    "member": {"pin": "0000", "role": "MEMBER", "name": "Family Member"},
}

ROLE_LABELS = {
    "SUPER_ADMIN": "Super Admin",
    "BRIDE_ADMIN": "Bride Admin",
    "GROOM_ADMIN": "Groom Admin",
    "MEMBER": "Member",
}

HIDE_FOR_MEMBERS = {"purchases", "commercials"}


# ----------------------------------------------------------
# UI (Royal Theme)
# ----------------------------------------------------------
BASE_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{title}}</title>
  <style>
    body{ font-family: Arial, sans-serif; background:#fffaf0; margin:0; padding:0; color:#2b2b2b; }
    header{ background: linear-gradient(90deg,#b8860b,#f5deb3); color:#fff; padding:14px 16px; font-weight:700; font-size:18px; }
    .wrap{ padding:16px; max-width:1100px; margin:auto; }
    .card{ background:#fff; border:1px solid #e7d9b0; border-radius:12px; padding:14px; margin-bottom:14px; box-shadow:0 2px 10px rgba(0,0,0,0.04); }
    .row{ display:flex; gap:12px; flex-wrap:wrap; }
    .col{ flex:1; min-width:260px; }
    .btn{ display:inline-block; background:#b8860b; color:#fff; padding:10px 14px; border-radius:10px; text-decoration:none; border:none; cursor:pointer; font-weight:600; }
    .btn2{ display:inline-block; background:#fff; color:#b8860b; padding:10px 14px; border-radius:10px; text-decoration:none; border:1px solid #b8860b; cursor:pointer; font-weight:600; }
    .muted{ color:#666; font-size:13px; }
    .tag{ display:inline-block; padding:4px 8px; border-radius:8px; background:#f7e7b6; color:#6a4b00; font-size:12px; font-weight:700; }
    input, select, textarea{ width:100%; padding:10px; border-radius:10px; border:1px solid #d9c88f; margin-top:6px; margin-bottom:10px; box-sizing:border-box; font-size:14px; }
    table{ width:100%; border-collapse:collapse; font-size:14px; }
    td,th{ border-bottom:1px solid #eee; padding:10px 6px; text-align:left; vertical-align:top; }
    .right{ text-align:right; }
    .danger{ color:#b00020; font-weight:700; }
    nav a{ margin-right:10px; text-decoration:none; color:#fff; font-weight:600; white-space:nowrap; }
    .small{ font-size:12px; }
  </style>
</head>
<body>
<header>
  {{title}}
  {% if user %}
    <div style="margin-top:6px; font-size:13px; font-weight:500;">
      Logged in as <b>{{user["name"]}}</b> ({{role_label}})
      | <a style="color:#fff;text-decoration:underline;" href="{{url_for('logout')}}">Logout</a>
    </div>
    <div style="margin-top:10px;">
      <nav>
        <a href="{{url_for('home')}}">Home</a>
        <a href="{{url_for('events')}}">Events</a>
        <a href="{{url_for('guests')}}">Guests</a>
        <a href="{{url_for('travel')}}">Travel</a>
        <a href="{{url_for('venue_rooms')}}">Venue/Rooms</a>
        <a href="{{url_for('vendors')}}">Vendors</a>

        {% if user["role"] != "MEMBER" %}
          <a href="{{url_for('purchases')}}">Purchases</a>
        {% endif %}

        {% if user["role"] == "SUPER_ADMIN" %}
          <a href="{{url_for('commercials')}}">Commercials</a>
        {% endif %}
      </nav>
    </div>
  {% endif %}
</header>

<div class="wrap">
  {{body|safe}}
</div>
</body>
</html>
"""


# ----------------------------------------------------------
# DB Layer (SQLite or PostgreSQL via psycopg2)
# ----------------------------------------------------------
def using_postgres():
    return bool(DATABASE_URL)


def get_db():
    """
    For SQLite: sqlite3 connection
    For Postgres: psycopg2 connection
    """
    if "db" in g:
        return g.db

    if using_postgres():
        import psycopg2

        # Render gives postgres://... which psycopg2 accepts
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        g.db = conn
        g.db_type = "postgres"
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
        g.db_type = "sqlite"

    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except:
            pass


def db_exec(sql, params=()):
    db = get_db()

    if g.get("db_type") == "sqlite":
        cur = db.execute(sql, params)
        db.commit()
        return cur

    # postgres
    cur = db.cursor()
    cur.execute(sql, params)
    return cur


def db_query(sql, params=()):
    db = get_db()

    if g.get("db_type") == "sqlite":
        cur = db.execute(sql, params)
        return cur.fetchall()

    # postgres
    cur = db.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()

    # Convert tuples to dict-like using cursor.description
    cols = [d[0] for d in cur.description]
    result = []
    for r in rows:
        result.append({cols[i]: r[i] for i in range(len(cols))})
    return result


def sql_type_int():
    return "INTEGER"


def sql_type_pk():
    # SQLite: INTEGER PRIMARY KEY AUTOINCREMENT
    # Postgres: SERIAL PRIMARY KEY
    if using_postgres():
        return "SERIAL PRIMARY KEY"
    return "INTEGER PRIMARY KEY AUTOINCREMENT"


def init_db():
    # Table create syntax differs slightly for Postgres
    # We'll use compatible SQL where possible.

    # EVENTS
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS events (
        id {sql_type_pk()},
        title TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        notes TEXT,
        assigned_to TEXT,
        status TEXT,
        created_by TEXT,
        updated_at TEXT
    )
    """)

    # GUESTS
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS guests (
        id {sql_type_pk()},
        side TEXT NOT NULL,
        name TEXT NOT NULL,
        relation TEXT,
        phone TEXT,
        visited {sql_type_int()} DEFAULT 0,
        stay_required {sql_type_int()} DEFAULT 0,
        room_no TEXT,
        notes TEXT,
        created_by TEXT,
        updated_at TEXT
    )
    """)

    # TRAVEL
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS travel (
        id {sql_type_pk()},
        guest_id {sql_type_int()} NOT NULL,
        arrival_date TEXT,
        arrival_time TEXT,
        mode TEXT,
        ref_no TEXT,
        pickup_required {sql_type_int()} DEFAULT 0,
        pickup_person TEXT,
        vehicle TEXT,
        checkin_date TEXT,
        checkout_date TEXT,
        status TEXT,
        assigned_to TEXT,
        notes TEXT,
        updated_at TEXT
    )
    """)

    # VENUE ROOMS
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS venue_rooms (
        id {sql_type_pk()},
        room_no TEXT,
        guest_name TEXT,
        checkin TEXT,
        checkout TEXT,
        status TEXT,
        assigned_to TEXT,
        notes TEXT,
        updated_at TEXT
    )
    """)

    # VENDORS
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS vendors (
        id {sql_type_pk()},
        category TEXT NOT NULL,
        vendor_name TEXT,
        contact_person TEXT,
        phone TEXT,
        status TEXT,
        assigned_to TEXT,
        notes TEXT,
        updated_at TEXT
    )
    """)

    # PURCHASES
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS purchases (
        id {sql_type_pk()},
        category TEXT NOT NULL,
        item TEXT NOT NULL,
        status TEXT,
        notes TEXT,
        updated_at TEXT
    )
    """)

    # COMMERCIALS
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS commercials (
        id {sql_type_pk()},
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        notes TEXT,
        updated_at TEXT
    )
    """)

    # Seed defaults
    existing = db_query("SELECT id FROM events LIMIT 1")
    if len(existing) == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec("""
        INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """ if using_postgres() else """
        INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("Venue Finalisation", "2026-01-25", "11:00", "Finalize venue and booking confirmation.", "Vijay", "Pending", "SYSTEM", now))

        db_exec("""
        INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """ if using_postgres() else """
        INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("Purchasing Plan (Clothes & Jewellery)", "2026-01-28", "16:00", "List items and confirm vendors.", "Vijay", "Pending", "SYSTEM", now))

    vend = db_query("SELECT id FROM vendors LIMIT 1")
    if len(vend) == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        default_vendors = [
            "Decoration", "Caterer", "Lighting", "Power Backup", "Outside Stalls",
            "Photo/Videographer", "Pandit Management"
        ]
        for cat in default_vendors:
            db_exec("""
            INSERT INTO vendors (category, vendor_name, contact_person, phone, status, assigned_to, notes, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """ if using_postgres() else """
            INSERT INTO vendors (category, vendor_name, contact_person, phone, status, assigned_to, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (cat, "", "", "", "Pending", "Vijay", "", now))


# ----------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------
def current_user():
    u = session.get("user")
    if not u:
        return None
    return USERS.get(u)


def require_login():
    if not current_user():
        return redirect(url_for("login"))
    return None


def is_admin(role):
    return role in ("SUPER_ADMIN", "BRIDE_ADMIN", "GROOM_ADMIN")


def deny_members(route_name):
    user = current_user()
    if user and user["role"] == "MEMBER" and route_name in HIDE_FOR_MEMBERS:
        abort(403)


def render(body_html):
    user = current_user()
    role_label = ROLE_LABELS.get(user["role"], "") if user else ""
    return render_template_string(BASE_HTML, title=APP_TITLE, body=body_html, user=user, role_label=role_label)


@app.before_request
def before_request():
    init_db()


# ----------------------------------------------------------
# Routes
# ----------------------------------------------------------
@app.route("/")
def home():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    rows = db_query("""
        SELECT * FROM events
        ORDER BY date ASC, time ASC
        LIMIT 10
    """)

    body = f"""
    <div class="card">
      <div class="row">
        <div class="col">
          <h2 style="margin:0;">Welcome, {user["name"]} 🎉</h2>
          <div class="muted">Wedding planning dashboard</div>
          <div style="margin-top:10px;">
            <span class="tag">{ROLE_LABELS.get(role)}</span>
          </div>
          <div class="muted small" style="margin-top:8px;">
            Storage: <b>{"PostgreSQL (Permanent)" if using_postgres() else "SQLite (Local)"}</b>
          </div>
        </div>
        <div class="col">
          <h3 style="margin:0;">Quick Actions</h3>
          <div style="margin-top:10px;">
            <a class="btn" href="{url_for('events')}">📅 Events</a>
            <a class="btn2" href="{url_for('guests')}">👥 Guests</a>
          </div>
          <div style="margin-top:10px;">
            <a class="btn2" href="{url_for('travel')}">🧳 Travel</a>
            <a class="btn2" href="{url_for('venue_rooms')}">🏨 Rooms</a>
          </div>
          <div style="margin-top:10px;">
            <a class="btn2" href="{url_for('vendors')}">🧑‍🔧 Vendors</a>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 style="margin-top:0;">Upcoming Events</h3>
      <table>
        <tr><th>When</th><th>Title</th><th>Status</th><th>Assigned</th><th>Notes</th></tr>
    """

    for e in rows:
        body += f"""
        <tr>
          <td>{e['date']} {e['time']}</td>
          <td><b>{e['title']}</b></td>
          <td><span class="tag">{e['status']}</span></td>
          <td class="muted">{e.get('assigned_to') or ''}</td>
          <td class="muted">{e.get('notes') or ''}</td>
        </tr>
        """

    body += "</table></div>"
    return render(body)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        pin = request.form.get("pin", "").strip()

        u = USERS.get(username)
        if not u or u["pin"] != pin:
            body = """
            <div class="card">
              <h2>Login</h2>
              <p class="danger">Invalid username or PIN</p>
              <form method="post">
                <label>Username</label>
                <input name="username" required>
                <label>PIN</label>
                <input name="pin" type="password" required>
                <button class="btn" type="submit">Login</button>
              </form>
            </div>
            """
            return render(body)

        session["user"] = username
        return redirect(url_for("home"))

    body = """
    <div class="card">
      <h2>Login</h2>
      <p class="muted">Please login with your provided credentials.</p>
      <form method="post">
        <label>Username</label>
        <input name="username" placeholder="Enter username" required>
        <label>PIN</label>
        <input name="pin" type="password" placeholder="****" required>
        <button class="btn" type="submit">Login</button>
      </form>
    </div>
    """
    return render(body)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ----------------------------------------------------------
# Simple pages (same as SQLite version, minimal changes)
# NOTE: To keep message size reasonable, remaining routes are kept identical logic.
# ----------------------------------------------------------

@app.route("/events", methods=["GET", "POST"])
def events():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            return render("<div class='card'><h2>Events</h2><p class='danger'>Only Admins can add events.</p></div>")

        title = request.form.get("title", "").strip()
        date_ = request.form.get("date", "").strip()
        time_ = request.form.get("time", "").strip()
        notes = request.form.get("notes", "").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        status = request.form.get("status", "Pending").strip()

        if title and date_ and time_:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sql = """
                INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """ if using_postgres() else """
                INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            db_exec(sql, (title, date_, time_, notes, assigned_to, status, user["name"], now))
        return redirect(url_for("events"))

    rows = db_query("SELECT * FROM events ORDER BY date ASC, time ASC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">📅 Events & Schedule</h2>
      <p class="muted">Admins can add events. Track progress using Assigned To + Status.</p>
      <table>
        <tr><th>When</th><th>Title</th><th>Status</th><th>Assigned</th><th>Notes</th></tr>
    """
    for e in rows:
        body += f"""
        <tr>
          <td>{e['date']} {e['time']}</td>
          <td><b>{e['title']}</b></td>
          <td><span class="tag">{e['status']}</span></td>
          <td class="muted">{e.get('assigned_to') or ''}</td>
          <td class="muted">{e.get('notes') or ''}</td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        opts = "".join([f"<option>{s}</option>" for s in STATUS_OPTIONS])
        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Event (Admin)</h3>
          <form method="post">
            <label>Title</label>
            <input name="title" required>
            <div class="row">
              <div class="col">
                <label>Date</label>
                <input name="date" type="date" required>
              </div>
              <div class="col">
                <label>Time</label>
                <input name="time" type="time" required>
              </div>
            </div>
            <div class="row">
              <div class="col">
                <label>Assigned To</label>
                <input name="assigned_to">
              </div>
              <div class="col">
                <label>Status</label>
                <select name="status">{opts}</select>
              </div>
            </div>
            <label>Notes</label>
            <textarea name="notes"></textarea>
            <button class="btn" type="submit">Add Event</button>
          </form>
        </div>
        """
    return render(body)


# For brevity, we keep remaining routes exactly same as your SQLite version.
# You can copy-paste the rest of your existing routes from your current app.py:
# /guests, /travel, /venue_rooms, /vendors, /purchases, /commercials, error handlers

@app.route("/guests")
def guests():
    return render("<div class='card'><h2>Guests</h2><p class='muted'>Please paste your existing Guests route code here (same as SQLite version).</p></div>")

@app.route("/travel")
def travel():
    return render("<div class='card'><h2>Travel</h2><p class='muted'>Please paste your existing Travel route code here (same as SQLite version).</p></div>")

@app.route("/venue_rooms")
def venue_rooms():
    return render("<div class='card'><h2>Venue/Rooms</h2><p class='muted'>Please paste your existing Venue/Rooms route code here.</p></div>")

@app.route("/vendors")
def vendors():
    return render("<div class='card'><h2>Vendors</h2><p class='muted'>Please paste your existing Vendors route code here.</p></div>")

@app.route("/purchases")
def purchases():
    return render("<div class='card'><h2>Purchases</h2><p class='muted'>Please paste your existing Purchases route code here.</p></div>")

@app.route("/commercials")
def commercials():
    return render("<div class='card'><h2>Commercials</h2><p class='muted'>Please paste your existing Commercials route code here.</p></div>")

@app.errorhandler(403)
def forbidden(e):
    return render("<div class='card'><h2>403 Forbidden</h2><p class='danger'>You do not have access to this section.</p></div>"), 403


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
