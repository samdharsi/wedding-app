import os
import sqlite3
from datetime import datetime

from flask import Flask, request, redirect, url_for, session, render_template_string, g, abort

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "wedding-secret-key-change-me")

APP_TITLE = "Nidhi & Tushar Wedding"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()  # Render Postgres URL
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

# Members should NOT see these:
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
    body{
      font-family: Arial, sans-serif;
      background: #fffaf0;
      margin:0;
      padding:0;
      color:#2b2b2b;
    }
    header{
      background: linear-gradient(90deg,#b8860b,#f5deb3);
      color:#fff;
      padding:14px 16px;
      font-weight:700;
      font-size:18px;
    }
    .wrap{ padding:16px; max-width:1100px; margin:auto; }
    .card{
      background:#ffffff;
      border:1px solid #e7d9b0;
      border-radius:12px;
      padding:14px;
      margin-bottom:14px;
      box-shadow:0 2px 10px rgba(0,0,0,0.04);
    }
    .row{ display:flex; gap:12px; flex-wrap:wrap; }
    .col{ flex:1; min-width:260px; }
    .btn{
      display:inline-block;
      background:#b8860b;
      color:#fff;
      padding:10px 14px;
      border-radius:10px;
      text-decoration:none;
      border:none;
      cursor:pointer;
      font-weight:600;
    }
    .btn2{
      display:inline-block;
      background:#fff;
      color:#b8860b;
      padding:10px 14px;
      border-radius:10px;
      text-decoration:none;
      border:1px solid #b8860b;
      cursor:pointer;
      font-weight:600;
    }
    .muted{ color:#666; font-size:13px; }
    .tag{
      display:inline-block;
      padding:4px 8px;
      border-radius:8px;
      background:#f7e7b6;
      color:#6a4b00;
      font-size:12px;
      font-weight:700;
    }
    input, select, textarea{
      width:100%;
      padding:10px;
      border-radius:10px;
      border:1px solid #d9c88f;
      margin-top:6px;
      margin-bottom:10px;
      box-sizing:border-box;
      font-size:14px;
    }
    table{
      width:100%;
      border-collapse:collapse;
      font-size:14px;
    }
    td,th{
      border-bottom:1px solid #eee;
      padding:10px 6px;
      text-align:left;
      vertical-align:top;
    }
    .right{ text-align:right; }
    .danger{ color:#b00020; font-weight:700; }
    nav a{
      margin-right:10px;
      text-decoration:none;
      color:#fff;
      font-weight:600;
      white-space:nowrap;
    }
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
# DB helpers (SQLite + Postgres)
# ----------------------------------------------------------
def using_postgres():
    return bool(DATABASE_URL)


def _ph(sql: str) -> str:
    """
    Convert SQLite placeholders (?) to Postgres placeholders (%s) if needed.
    """
    if not using_postgres():
        return sql
    return sql.replace("?", "%s")


def get_db():
    if "db" in g:
        return g.db

    if using_postgres():
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        g.db = conn
        g.db_type = "postgres"
        return conn

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    g.db = conn
    g.db_type = "sqlite"
    return conn


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
    sql = _ph(sql)

    if g.get("db_type") == "sqlite":
        cur = db.execute(sql, params)
        db.commit()
        return cur

    cur = db.cursor()
    cur.execute(sql, params)
    return cur


def db_query(sql, params=()):
    db = get_db()
    sql = _ph(sql)

    if g.get("db_type") == "sqlite":
        cur = db.execute(sql, params)
        return cur.fetchall()

    cur = db.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    out = []
    for r in rows:
        out.append({cols[i]: r[i] for i in range(len(cols))})
    return out


def sql_pk():
    return "SERIAL PRIMARY KEY" if using_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"


def sql_int():
    return "INTEGER"


def init_db():
    # EVENTS
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS events (
        id {sql_pk()},
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
        id {sql_pk()},
        side TEXT NOT NULL,
        name TEXT NOT NULL,
        relation TEXT,
        phone TEXT,
        visited {sql_int()} DEFAULT 0,
        stay_required {sql_int()} DEFAULT 0,
        room_no TEXT,
        notes TEXT,
        created_by TEXT,
        updated_at TEXT
    )
    """)

    # TRAVEL
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS travel (
        id {sql_pk()},
        guest_id {sql_int()} NOT NULL,
        arrival_date TEXT,
        arrival_time TEXT,
        mode TEXT,
        ref_no TEXT,
        pickup_required {sql_int()} DEFAULT 0,
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
        id {sql_pk()},
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
        id {sql_pk()},
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
        id {sql_pk()},
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
        id {sql_pk()},
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        notes TEXT,
        updated_at TEXT
    )
    """)

    # Seed
    if len(db_query("SELECT id FROM events LIMIT 1")) == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec("""
            INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Venue Finalisation", "2026-01-25", "11:00", "Finalize venue and booking confirmation.", "Vijay", "Pending", "SYSTEM", now))

        db_exec("""
            INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Purchasing Plan (Clothes & Jewellery)", "2026-01-28", "16:00", "List items and confirm vendors.", "Vijay", "Pending", "SYSTEM", now))

    if len(db_query("SELECT id FROM vendors LIMIT 1")) == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        default_vendors = [
            "Decoration", "Caterer", "Lighting", "Power Backup", "Outside Stalls",
            "Photo/Videographer", "Pandit Management"
        ]
        for cat in default_vendors:
            db_exec("""
                INSERT INTO vendors (category, vendor_name, contact_person, phone, status, assigned_to, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cat, "", "", "", "Pending", "Vijay", "", now))


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

    upcoming = db_query("""
        SELECT * FROM events
        ORDER BY date ASC, time ASC
        LIMIT 10
    """)

    storage = "PostgreSQL (Permanent)" if using_postgres() else "SQLite (Local)"

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
            Storage: <b>{storage}</b>
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
        <tr>
          <th>When</th><th>Title</th><th>Status</th><th>Assigned</th><th>Notes</th>
        </tr>
    """

    for e in upcoming:
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


# ------------------------- EVENTS -------------------------
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
            db_exec("""
                INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, date_, time_, notes, assigned_to, status, user["name"], now))
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
            <input name="title" placeholder="e.g., Haldi, Venue check-in, Shopping" required>

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
                <input name="assigned_to" placeholder="Vijay / Samdharsi / Tushar / Other">
              </div>
              <div class="col">
                <label>Status</label>
                <select name="status">{opts}</select>
              </div>
            </div>

            <label>Notes</label>
            <textarea name="notes" placeholder="Optional notes..."></textarea>

            <button class="btn" type="submit">Add Event</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>You have view-only access.</p></div>"

    return render(body)


# ------------------------- GUESTS -------------------------
@app.route("/guests", methods=["GET", "POST"])
def guests():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "add":
            if not is_admin(role):
                return render("<div class='card'><h2>Guests</h2><p class='danger'>Only Admins can add guests.</p></div>")

            side = request.form.get("side", "BRIDE").strip().upper()
            name = request.form.get("name", "").strip()
            relation = request.form.get("relation", "").strip()
            phone = request.form.get("phone", "").strip()
            stay_required = 1 if request.form.get("stay_required") == "on" else 0
            room_no = request.form.get("room_no", "").strip()
            notes = request.form.get("notes", "").strip()

            if name:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_exec("""
                    INSERT INTO guests (side, name, relation, phone, visited, stay_required, room_no, notes, created_by, updated_at)
                    VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
                """, (side, name, relation, phone, stay_required, room_no, notes, user["name"], now))
            return redirect(url_for("guests"))

        if action == "toggle_visit":
            gid = int(request.form.get("gid"))
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db_exec("""
                UPDATE guests
                SET visited = CASE visited WHEN 1 THEN 0 ELSE 1 END,
                    updated_at = ?
                WHERE id = ?
            """, (now, gid))
            return redirect(url_for("guests"))

    rows = db_query("SELECT * FROM guests ORDER BY side ASC, name ASC")
    bride = [g for g in rows if g["side"] == "BRIDE"]
    groom = [g for g in rows if g["side"] == "GROOM"]

    def guest_table(title, items):
        html = f"""
        <div class="card">
          <h3 style="margin-top:0;">{title}</h3>
          <table>
            <tr><th>Name</th><th>Relation</th><th>Stay</th><th>Room</th><th>Visited</th><th class="right">Action</th></tr>
        """
        for g1 in items:
            visited = "✅" if g1["visited"] else "—"
            stay = "Yes" if g1["stay_required"] else "No"
            html += f"""
            <tr>
              <td><b>{g1['name']}</b><div class="muted small">{g1.get('phone') or ''}</div></td>
              <td class="muted">{g1.get('relation') or ''}</td>
              <td>{stay}</td>
              <td class="muted">{g1.get('room_no') or ''}</td>
              <td>{visited}</td>
              <td class="right">
                <form method="post" style="margin:0;">
                  <input type="hidden" name="action" value="toggle_visit">
                  <input type="hidden" name="gid" value="{g1['id']}">
                  <button class="btn2" type="submit">Toggle</button>
                </form>
              </td>
            </tr>
            """
        html += "</table></div>"
        return html

    body = """
    <div class="card">
      <h2 style="margin-top:0;">👥 Guest Management</h2>
      <p class="muted">Guests are separated Bride-side / Groom-side. Travel is managed guest-wise in Travel section.</p>
    </div>
    <div class="row">
      <div class="col">
    """
    body += guest_table("Bride Side", bride)
    body += """
      </div>
      <div class="col">
    """
    body += guest_table("Groom Side", groom)
    body += """
      </div>
    </div>
    """

    if is_admin(role):
        body += """
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Guest (Admin)</h3>
          <form method="post">
            <input type="hidden" name="action" value="add">

            <label>Side</label>
            <select name="side">
              <option value="BRIDE">Bride Side</option>
              <option value="GROOM">Groom Side</option>
            </select>

            <label>Name</label>
            <input name="name" placeholder="Guest name" required>

            <div class="row">
              <div class="col">
                <label>Relation</label>
                <input name="relation" placeholder="e.g., Uncle, Friend, Cousin">
              </div>
              <div class="col">
                <label>Phone (optional)</label>
                <input name="phone" placeholder="+91...">
              </div>
            </div>

            <label>Stay Required?</label>
            <input type="checkbox" name="stay_required"> Yes

            <label>Room No (optional)</label>
            <input name="room_no" placeholder="e.g., 101 / A-12">

            <label>Notes</label>
            <input name="notes" placeholder="Optional notes...">

            <button class="btn" type="submit">Add Guest</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>You have view-only access.</p></div>"

    return render(body)


# ------------------------- TRAVEL -------------------------
@app.route("/travel", methods=["GET", "POST"])
def travel():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            return render("<div class='card'><h2>Travel</h2><p class='danger'>Only Admins can update travel details.</p></div>")

        guest_id = int(request.form.get("guest_id"))
        arrival_date = request.form.get("arrival_date", "").strip()
        arrival_time = request.form.get("arrival_time", "").strip()
        mode = request.form.get("mode", "").strip()
        ref_no = request.form.get("ref_no", "").strip()
        pickup_required = 1 if request.form.get("pickup_required") == "on" else 0
        pickup_person = request.form.get("pickup_person", "").strip()
        vehicle = request.form.get("vehicle", "").strip()
        checkin_date = request.form.get("checkin_date", "").strip()
        checkout_date = request.form.get("checkout_date", "").strip()
        status = request.form.get("status", "Pending").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        notes = request.form.get("notes", "").strip()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        existing = db_query("SELECT id FROM travel WHERE guest_id = ?", (guest_id,))
        if existing:
            db_exec("""
                UPDATE travel
                SET arrival_date=?, arrival_time=?, mode=?, ref_no=?, pickup_required=?, pickup_person=?, vehicle=?,
                    checkin_date=?, checkout_date=?, status=?, assigned_to=?, notes=?, updated_at=?
                WHERE guest_id=?
            """, (arrival_date, arrival_time, mode, ref_no, pickup_required, pickup_person, vehicle,
                  checkin_date, checkout_date, status, assigned_to, notes, now, guest_id))
        else:
            db_exec("""
                INSERT INTO travel (guest_id, arrival_date, arrival_time, mode, ref_no, pickup_required, pickup_person, vehicle,
                                   checkin_date, checkout_date, status, assigned_to, notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (guest_id, arrival_date, arrival_time, mode, ref_no, pickup_required, pickup_person, vehicle,
                  checkin_date, checkout_date, status, assigned_to, notes, now))

        return redirect(url_for("travel"))

    guests_rows = db_query("SELECT * FROM guests ORDER BY side ASC, name ASC")
    travel_rows = db_query("""
        SELECT t.*, g.name as guest_name, g.side as guest_side
        FROM travel t
        JOIN guests g ON g.id = t.guest_id
        ORDER BY g.side ASC, g.name ASC
    """)

    travel_map = {r["guest_id"]: r for r in travel_rows}

    body = """
    <div class="card">
      <h2 style="margin-top:0;">🧳 Guest-wise Travel & Stay</h2>
      <p class="muted">Each guest can have arrival details, pickup, and stay schedule. Admins can update.</p>
    </div>
    """

    body += """
    <div class="card">
      <h3 style="margin-top:0;">Travel Summary</h3>
      <table>
        <tr>
          <th>Guest</th><th>Arrival</th><th>Pickup</th><th>Stay</th><th>Status</th><th>Assigned</th><th>Notes</th>
        </tr>
    """
    for g1 in guests_rows:
        t = travel_map.get(g1["id"])
        if t:
            arrival = f"{t.get('arrival_date') or ''} {t.get('arrival_time') or ''} ({t.get('mode') or ''}) {t.get('ref_no') or ''}"
            pickup = "Yes" if t.get("pickup_required") else "No"
            stay = f"{t.get('checkin_date') or ''} → {t.get('checkout_date') or ''}"
            status = t.get("status") or "Pending"
            assigned = t.get("assigned_to") or ""
            notes = t.get("notes") or ""
        else:
            arrival = "—"
            pickup = "—"
            stay = "—"
            status = "Pending"
            assigned = ""
            notes = ""
        body += f"""
        <tr>
          <td><b>{g1['name']}</b><div class="muted small">{g1['side']}</div></td>
          <td class="muted">{arrival}</td>
          <td>{pickup}</td>
          <td class="muted">{stay}</td>
          <td><span class="tag">{status}</span></td>
          <td class="muted">{assigned}</td>
          <td class="muted">{notes}</td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        opts = "".join([f"<option>{s}</option>" for s in STATUS_OPTIONS])
        guest_opts = "".join([f"<option value='{g2['id']}'>{g2['name']} ({g2['side']})</option>" for g2 in guests_rows])

        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add / Update Travel (Admin)</h3>
          <form method="post">
            <label>Guest</label>
            <select name="guest_id" required>
              {guest_opts}
            </select>

            <div class="row">
              <div class="col">
                <label>Arrival Date</label>
                <input name="arrival_date" type="date">
              </div>
              <div class="col">
                <label>Arrival Time</label>
                <input name="arrival_time" type="time">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label>Mode</label>
                <select name="mode">
                  <option value="">--</option>
                  <option>Train</option>
                  <option>Flight</option>
                  <option>Car</option>
                  <option>Bus</option>
                  <option>Other</option>
                </select>
              </div>
              <div class="col">
                <label>Ref No (Train/Flight No)</label>
                <input name="ref_no" placeholder="e.g., 12951 / AI-101">
              </div>
            </div>

            <label>Pickup Required?</label>
            <input type="checkbox" name="pickup_required"> Yes

            <div class="row">
              <div class="col">
                <label>Pickup Person</label>
                <input name="pickup_person" placeholder="Who will pickup?">
              </div>
              <div class="col">
                <label>Vehicle</label>
                <input name="vehicle" placeholder="Car/Driver details">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label>Check-in Date</label>
                <input name="checkin_date" type="date">
              </div>
              <div class="col">
                <label>Check-out Date</label>
                <input name="checkout_date" type="date">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label>Status</label>
                <select name="status">{opts}</select>
              </div>
              <div class="col">
                <label>Assigned To</label>
                <input name="assigned_to" placeholder="Vijay / Samdharsi / Tushar / Other">
              </div>
            </div>

            <label>Notes</label>
            <input name="notes" placeholder="Food preference / special needs / remarks">

            <button class="btn" type="submit">Save Travel</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>You have view-only access.</p></div>"

    return render(body)


# ------------------------- VENUE / ROOMS -------------------------
@app.route("/venue_rooms", methods=["GET", "POST"])
def venue_rooms():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            return render("<div class='card'><h2>Venue/Rooms</h2><p class='danger'>Only Admins can update rooms.</p></div>")

        room_no = request.form.get("room_no", "").strip()
        guest_name = request.form.get("guest_name", "").strip()
        checkin = request.form.get("checkin", "").strip()
        checkout = request.form.get("checkout", "").strip()
        status = request.form.get("status", "Pending").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        notes = request.form.get("notes", "").strip()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec("""
            INSERT INTO venue_rooms (room_no, guest_name, checkin, checkout, status, assigned_to, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (room_no, guest_name, checkin, checkout, status, assigned_to, notes, now))

        return redirect(url_for("venue_rooms"))

    rows = db_query("SELECT * FROM venue_rooms ORDER BY id DESC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">🏨 Venue / Rooms Check-in & Check-out</h2>
      <p class="muted">Track room allocations and check-in/out status.</p>
    </div>

    <div class="card">
      <h3 style="margin-top:0;">Room Entries</h3>
      <table>
        <tr><th>Room</th><th>Guest</th><th>Check-in</th><th>Check-out</th><th>Status</th><th>Assigned</th><th>Notes</th></tr>
    """
    for r1 in rows:
        body += f"""
        <tr>
          <td><b>{r1.get('room_no') or ''}</b></td>
          <td class="muted">{r1.get('guest_name') or ''}</td>
          <td class="muted">{r1.get('checkin') or ''}</td>
          <td class="muted">{r1.get('checkout') or ''}</td>
          <td><span class="tag">{r1.get('status')}</span></td>
          <td class="muted">{r1.get('assigned_to') or ''}</td>
          <td class="muted">{r1.get('notes') or ''}</td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        opts = "".join([f"<option>{s}</option>" for s in STATUS_OPTIONS])
        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Room Entry (Admin)</h3>
          <form method="post">
            <div class="row">
              <div class="col">
                <label>Room No</label>
                <input name="room_no" placeholder="e.g., 101 / A-12">
              </div>
              <div class="col">
                <label>Guest Name</label>
                <input name="guest_name" placeholder="Guest name (optional)">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label>Check-in</label>
                <input name="checkin" placeholder="e.g., 19-Feb 11:00 AM">
              </div>
              <div class="col">
                <label>Check-out</label>
                <input name="checkout" placeholder="e.g., 21-Feb 09:00 AM">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label>Status</label>
                <select name="status">{opts}</select>
              </div>
              <div class="col">
                <label>Assigned To</label>
                <input name="assigned_to" placeholder="Vijay / Samdharsi / Tushar / Other">
              </div>
            </div>

            <label>Notes</label>
            <input name="notes" placeholder="Key handover / issues / remarks">

            <button class="btn" type="submit">Add Room Entry</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>You have view-only access.</p></div>"

    return render(body)


# ------------------------- VENDORS -------------------------
@app.route("/vendors", methods=["GET", "POST"])
def vendors():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            return render("<div class='card'><h2>Vendors</h2><p class='danger'>Only Admins can update vendors.</p></div>")

        category = request.form.get("category", "").strip()
        vendor_name = request.form.get("vendor_name", "").strip()
        contact_person = request.form.get("contact_person", "").strip()
        phone = request.form.get("phone", "").strip()
        status = request.form.get("status", "Pending").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        notes = request.form.get("notes", "").strip()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec("""
            INSERT INTO vendors (category, vendor_name, contact_person, phone, status, assigned_to, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (category, vendor_name, contact_person, phone, status, assigned_to, notes, now))

        return redirect(url_for("vendors"))

    rows = db_query("SELECT * FROM vendors ORDER BY category ASC, id DESC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">🧑‍🔧 Vendor Management</h2>
      <p class="muted">Decoration, Caterer, Lighting, Power backup, Photo/Videographer, Pandit, etc.</p>
    </div>

    <div class="card">
      <h3 style="margin-top:0;">Vendor Entries</h3>
      <table>
        <tr><th>Category</th><th>Vendor</th><th>Contact</th><th>Status</th><th>Assigned</th><th>Notes</th></tr>
    """
    for v in rows:
        contact = f"{v.get('contact_person') or ''} {v.get('phone') or ''}".strip()
        body += f"""
        <tr>
          <td><b>{v.get('category')}</b></td>
          <td class="muted">{v.get('vendor_name') or ''}</td>
          <td class="muted">{contact}</td>
          <td><span class="tag">{v.get('status')}</span></td>
          <td class="muted">{v.get('assigned_to') or ''}</td>
          <td class="muted">{v.get('notes') or ''}</td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        opts = "".join([f"<option>{s}</option>" for s in STATUS_OPTIONS])
        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Vendor Entry (Admin)</h3>
          <form method="post">
            <label>Category</label>
            <select name="category" required>
              <option>Decoration</option>
              <option>Caterer</option>
              <option>Lighting</option>
              <option>Power Backup</option>
              <option>Outside Stalls</option>
              <option>Photo/Videographer</option>
              <option>Pandit Management</option>
              <option>Other</option>
            </select>

            <label>Vendor Name</label>
            <input name="vendor_name" placeholder="Vendor company/person">

            <div class="row">
              <div class="col">
                <label>Contact Person</label>
                <input name="contact_person" placeholder="Name">
              </div>
              <div class="col">
                <label>Phone</label>
                <input name="phone" placeholder="+91...">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label>Status</label>
                <select name="status">{opts}</select>
              </div>
              <div class="col">
                <label>Assigned To</label>
                <input name="assigned_to" placeholder="Vijay / Samdharsi / Tushar / Other">
              </div>
            </div>

            <label>Notes</label>
            <input name="notes" placeholder="Timing / requirements / remarks">

            <button class="btn" type="submit">Add Vendor</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>You have view-only access.</p></div>"

    return render(body)


# ------------------------- PURCHASES (Hidden from Members) -------------------------
@app.route("/purchases", methods=["GET", "POST"])
def purchases():
    r = require_login()
    if r:
        return r

    deny_members("purchases")

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            return render("<div class='card'><h2>Purchases</h2><p class='danger'>Only Admins can add purchases.</p></div>")

        category = request.form.get("category", "").strip()
        item = request.form.get("item", "").strip()
        status = request.form.get("status", "Pending").strip()
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if category and item:
            db_exec("""
                INSERT INTO purchases (category, item, status, notes, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (category, item, status, notes, now))

        return redirect(url_for("purchases"))

    rows = db_query("SELECT * FROM purchases ORDER BY id DESC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">🛍 Purchases (Hidden from Members)</h2>
      <p class="muted">Admins can track purchases here.</p>
      <table>
        <tr><th>Category</th><th>Item</th><th>Status</th><th>Notes</th></tr>
    """
    for p in rows:
        body += f"""
        <tr>
          <td><b>{p.get('category')}</b></td>
          <td>{p.get('item')}</td>
          <td><span class="tag">{p.get('status')}</span></td>
          <td class="muted">{p.get('notes') or ''}</td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        opts = "".join([f"<option>{s}</option>" for s in STATUS_OPTIONS])
        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Purchase (Admin)</h3>
          <form method="post">
            <label>Category</label>
            <select name="category">
              <option>Clothes</option>
              <option>Jewellery</option>
              <option>Travel</option>
              <option>Gifts</option>
              <option>Misc</option>
            </select>

            <label>Item</label>
            <input name="item" placeholder="e.g., Saree, Shoes, Ring" required>

            <label>Status</label>
            <select name="status">{opts}</select>

            <label>Notes</label>
            <input name="notes" placeholder="Optional notes...">

            <button class="btn" type="submit">Add Purchase</button>
          </form>
        </div>
        """
    return render(body)


# ------------------------- COMMERCIALS (Super Admin only) -------------------------
@app.route("/commercials", methods=["GET", "POST"])
def commercials():
    r = require_login()
    if r:
        return r

    user = current_user()
    if user["role"] != "SUPER_ADMIN":
        return render("<div class='card'><h2>Commercials</h2><p class='danger'>Access denied.</p></div>")

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        amount = request.form.get("amount", "").strip()
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            amt = float(amount)
        except:
            amt = None

        if category and amt is not None:
            db_exec("""
                INSERT INTO commercials (category, amount, notes, updated_at)
                VALUES (?, ?, ?, ?)
            """, (category, amt, notes, now))

        return redirect(url_for("commercials"))

    rows = db_query("SELECT * FROM commercials ORDER BY id DESC")
    total = sum([r.get("amount", 0) for r in rows]) if rows else 0

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">💰 Commercials (Super Admin Only)</h2>
      <p class="muted">Hidden from admins and members.</p>
      <table>
        <tr><th>Category</th><th class="right">Amount</th><th>Notes</th></tr>
    """
    for c in rows:
        body += f"""
        <tr>
          <td><b>{c.get('category')}</b></td>
          <td class="right">₹ {c.get('amount')}</td>
          <td class="muted">{c.get('notes') or ''}</td>
        </tr>
        """
    body += f"""
      </table>
      <h3 style="margin-top:14px;">Total: ₹ {total}</h3>
    </div>

    <div class="card">
      <h3 style="margin-top:0;">➕ Add Commercial Entry</h3>
      <form method="post">
        <label>Category</label>
        <input name="category" placeholder="e.g., Venue Advance" required>
        <label>Amount</label>
        <input name="amount" placeholder="250000" required>
        <label>Notes</label>
        <input name="notes" placeholder="Optional notes...">
        <button class="btn" type="submit">Add</button>
      </form>
    </div>
    """
    return render(body)


# ----------------------------------------------------------
# Error handler
# ----------------------------------------------------------
@app.errorhandler(403)
def forbidden(e):
    return render("<div class='card'><h2>403 Forbidden</h2><p class='danger'>You do not have access to this section.</p></div>"), 403


# ----------------------------------------------------------
# Run
# ----------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)


