import os
import sqlite3
from datetime import datetime

from flask import (
    Flask, request, redirect, url_for, session,
    render_template_string, g, abort, flash
)

# ----------------------------------------------------------
# APP CONFIG
# ----------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "wedding-secret-key-change-me")

APP_TITLE = "Nidhi & Tushar Wedding"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SQLITE_PATH = os.environ.get("DB_PATH", "wedding.db")

STATUS_OPTIONS = ["Pending", "In Progress", "Done"]
GUEST_SIDE_OPTIONS = ["Bride", "Groom"]
VENDOR_CATEGORIES = [
    "Decoration", "Caterer", "Lighting", "Power Backup",
    "Outside Stalls", "Photo/Videographer", "Pandit Management",
    "Makeup", "Mehendi", "Band/Baja", "Transport"
]
TRAVEL_MODE_OPTIONS = ["Car", "Train", "Flight", "Bus", "Other"]
NOTE_CATEGORIES = ["General", "Venue", "Guest", "Travel", "Vendor", "Purchase", "Puja", "Food", "Decoration"]

UPLOAD_CATEGORIES = ["Receipt", "Bill", "Photo", "Document", "Other"]

# ----------------------------------------------------------
# USERS / ROLES
# ----------------------------------------------------------
USERS = {
    "vijay": {"pin": "1234", "role": "SUPER_ADMIN", "name": "Vijay"},
    "samdharsi": {"pin": "1111", "role": "BRIDE_ADMIN", "name": "Samdharsi Kumar"},
    "nidhi": {"pin": "2222", "role": "BRIDE_ADMIN", "name": "Nidhi Sharma"},
    "guest": {"pin": "0000", "role": "MEMBER", "name": "Family Member"},
}

ROLE_LABELS = {
    "SUPER_ADMIN": "Super Admin",
    "BRIDE_ADMIN": "Bride Admin",
    "GROOM_ADMIN": "Groom Admin",
    "MEMBER": "Member",
}

# members cannot see purchases/commercials
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
    .wrap{ padding:16px; max-width:1300px; margin:auto; }
    .card{ background:#fff; border:1px solid #e7d9b0; border-radius:12px; padding:14px; margin-bottom:14px; box-shadow:0 2px 10px rgba(0,0,0,0.04); }
    .row{ display:flex; gap:12px; flex-wrap:wrap; }
    .col{ flex:1; min-width:260px; }
    .btn{ display:inline-block; background:#b8860b; color:#fff; padding:10px 14px; border-radius:10px; text-decoration:none; border:none; cursor:pointer; font-weight:600; }
    .btn2{ display:inline-block; background:#fff; color:#b8860b; padding:10px 14px; border-radius:10px; text-decoration:none; border:1px solid #b8860b; cursor:pointer; font-weight:600; }
    .btnDanger{ display:inline-block; background:#b00020; color:#fff; padding:8px 12px; border-radius:10px; text-decoration:none; border:none; cursor:pointer; font-weight:700; }
    .btnSmall{ padding:7px 10px; border-radius:10px; font-size:13px; }
    .muted{ color:#666; font-size:13px; }
    .tag{ display:inline-block; padding:4px 8px; border-radius:8px; background:#f7e7b6; color:#6a4b00; font-size:12px; font-weight:700; }
    input, select, textarea{ width:100%; padding:10px; border-radius:10px; border:1px solid #d9c88f; margin-top:6px; margin-bottom:10px; box-sizing:border-box; font-size:14px; }
    table{ width:100%; border-collapse:collapse; font-size:14px; }
    td,th{ border-bottom:1px solid #eee; padding:10px 6px; text-align:left; vertical-align:top; }
    .right{ text-align:right; }
    .danger{ color:#b00020; font-weight:700; }
    nav a{ margin-right:10px; text-decoration:none; color:#fff; font-weight:600; white-space:nowrap; }
    .small{ font-size:12px; }
    .flash{ background:#e8ffe8; border:1px solid #86d786; padding:10px; border-radius:10px; margin-bottom:12px; }
    .flashErr{ background:#ffe8e8; border:1px solid #d78686; padding:10px; border-radius:10px; margin-bottom:12px; }
    .actions{ white-space:nowrap; }
    .pill{ display:inline-block; padding:4px 10px; border-radius:999px; background:#f3f3f3; border:1px solid #ddd; font-size:12px; }
    .grid2{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    @media (max-width: 850px){
      .grid2{ grid-template-columns:1fr; }
    }
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
        <a href="{{url_for('vendors')}}">Vendors</a>
        <a href="{{url_for('venue_rooms')}}">Venue/Rooms</a>
        <a href="{{url_for('notes')}}">Notes</a>
        <a href="{{url_for('uploads')}}">Uploads</a>

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
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for cat,msg in messages %}
        <div class="{{'flashErr' if cat=='error' else 'flash'}}">{{msg}}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}
  {{body|safe}}
</div>
</body>
</html>
"""


# ----------------------------------------------------------
# DB Helpers (SQLite / Postgres via psycopg3)
# ----------------------------------------------------------
def using_postgres():
    return bool(DATABASE_URL)


def get_db():
    if "db" in g:
        return g.db

    if using_postgres():
        import psycopg
        conn = psycopg.connect(DATABASE_URL)
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


def _ph():
    return "%s" if using_postgres() else "?"


def db_exec(sql, params=()):
    db = get_db()
    if g.get("db_type") == "sqlite":
        cur = db.execute(sql, params)
        db.commit()
        return cur

    cur = db.cursor()
    cur.execute(sql, params)
    return cur


def db_query(sql, params=()):
    db = get_db()

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
    if using_postgres():
        return "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
    return "INTEGER PRIMARY KEY AUTOINCREMENT"


def safe_int(v, default=0):
    try:
        return int(v)
    except:
        return default


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
        visited INTEGER DEFAULT 0,
        stay_required INTEGER DEFAULT 0,
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
        guest_id INTEGER NOT NULL,
        arrival_date TEXT,
        arrival_time TEXT,
        mode TEXT,
        ref_no TEXT,
        pickup_required INTEGER DEFAULT 0,
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

    # PURCHASES (Admins only)
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS purchases (
        id {sql_pk()},
        category TEXT NOT NULL,
        item TEXT NOT NULL,
        amount REAL DEFAULT 0,
        status TEXT,
        notes TEXT,
        updated_at TEXT
    )
    """)

    # COMMERCIALS (Super Admin only)
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS commercials (
        id {sql_pk()},
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        notes TEXT,
        updated_at TEXT
    )
    """)

    # NOTES
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS notes (
        id {sql_pk()},
        category TEXT,
        title TEXT,
        content TEXT,
        created_by TEXT,
        updated_at TEXT
    )
    """)

    # UPLOADS (Google Drive links)
    db_exec(f"""
    CREATE TABLE IF NOT EXISTS uploads (
        id {sql_pk()},
        category TEXT,
        title TEXT,
        drive_link TEXT,
        notes TEXT,
        uploaded_by TEXT,
        updated_at TEXT
    )
    """)

    # seed
    existing = db_query("SELECT id FROM events LIMIT 1")
    if len(existing) == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec(
            f"INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
            ("Venue Finalisation", "2026-01-25", "11:00", "Finalize venue and booking confirmation.", "Vijay", "Pending", "SYSTEM", now),
        )

    vend = db_query("SELECT id FROM vendors LIMIT 1")
    if len(vend) == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for cat in VENDOR_CATEGORIES:
            db_exec(
                f"INSERT INTO vendors (category, vendor_name, contact_person, phone, status, assigned_to, notes, updated_at) "
                f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
                (cat, "", "", "", "Pending", "Vijay", "", now),
            )


@app.before_request
def before_request():
    init_db()


# ----------------------------------------------------------
# Auth
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


def can_delete(role):
    # as per your choice B
    return role in ("SUPER_ADMIN", "BRIDE_ADMIN", "GROOM_ADMIN")


def render(body_html):
    user = current_user()
    role_label = ROLE_LABELS.get(user["role"], "") if user else ""
    return render_template_string(BASE_HTML, title=APP_TITLE, body=body_html, user=user, role_label=role_label)


# ----------------------------------------------------------
# ROUTES
# ----------------------------------------------------------
@app.route("/")
def home():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    upcoming = db_query("SELECT * FROM events ORDER BY date ASC, time ASC LIMIT 8")
    guests_count = db_query("SELECT COUNT(*) AS c FROM guests")
    vendors_count = db_query("SELECT COUNT(*) AS c FROM vendors")
    rooms_count = db_query("SELECT COUNT(*) AS c FROM venue_rooms")
    travel_count = db_query("SELECT COUNT(*) AS c FROM travel")
    notes_count = db_query("SELECT COUNT(*) AS c FROM notes")
    uploads_count = db_query("SELECT COUNT(*) AS c FROM uploads")

    def _get_count(rows):
        if not rows:
            return 0
        if isinstance(rows[0], dict):
            return rows[0].get("c", 0)
        return rows[0]["c"]

    body = f"""
    <div class="card">
      <div class="row">
        <div class="col">
          <h2 style="margin:0;">Welcome, {user["name"]} 🎉</h2>
          <div class="muted">Wedding planning dashboard</div>
          <div style="margin-top:10px;">
            <span class="tag">{ROLE_LABELS.get(role)}</span>
            <span class="pill">Storage: {"PostgreSQL Permanent" if using_postgres() else "SQLite Local"}</span>
          </div>
        </div>
        <div class="col">
          <h3 style="margin:0;">Summary</h3>
          <div style="margin-top:10px;">
            👥 Guests: <b>{_get_count(guests_count)}</b><br>
            🧳 Travel: <b>{_get_count(travel_count)}</b><br>
            🧑‍🔧 Vendors: <b>{_get_count(vendors_count)}</b><br>
            🏨 Rooms: <b>{_get_count(rooms_count)}</b><br>
            📝 Notes: <b>{_get_count(notes_count)}</b><br>
            📎 Uploads: <b>{_get_count(uploads_count)}</b>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 style="margin-top:0;">Upcoming Events</h3>
      <table>
        <tr><th>When</th><th>Title</th><th>Status</th><th>Assigned</th></tr>
    """

    for e in upcoming:
        body += f"""
        <tr>
          <td>{e['date']} {e['time']}</td>
          <td><b>{e['title']}</b></td>
          <td><span class="tag">{e.get('status','')}</span></td>
          <td class="muted">{e.get('assigned_to','')}</td>
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
            flash("Invalid username or PIN", "error")
            return redirect(url_for("login"))

        session["user"] = username
        return redirect(url_for("home"))

    body = """
    <div class="card">
      <h2>Login</h2>
      <p class="muted">Please login with your provided credentials.</p>
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


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==========================================================
# EVENTS
# ==========================================================
@app.route("/events", methods=["GET", "POST"])
def events():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            flash("Only Admins can add events.", "error")
            return redirect(url_for("events"))

        title = request.form.get("title", "").strip()
        date_ = request.form.get("date", "").strip()
        time_ = request.form.get("time", "").strip()
        notes = request.form.get("notes", "").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        status = request.form.get("status", "Pending").strip()

        if not title or not date_ or not time_:
            flash("Title/Date/Time are required.", "error")
            return redirect(url_for("events"))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec(
            f"INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
            (title, date_, time_, notes, assigned_to, status, user["name"], now),
        )
        flash("Event added successfully ✅")
        return redirect(url_for("events"))

    rows = db_query("SELECT * FROM events ORDER BY date ASC, time ASC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">📅 Events & Schedule</h2>
      <table>
        <tr>
          <th>When</th><th>Title</th><th>Status</th><th>Assigned</th><th>Notes</th><th class="right">Actions</th>
        </tr>
    """
    for e in rows:
        body += f"""
        <tr>
          <td>{e['date']} {e['time']}</td>
          <td><b>{e['title']}</b></td>
          <td><span class="tag">{e.get('status','')}</span></td>
          <td class="muted">{e.get('assigned_to') or ''}</td>
          <td class="muted">{(e.get('notes') or '')[:80]}</td>
          <td class="right actions">
            <a class="btn2 btnSmall" href="{url_for('edit_event', event_id=e['id'])}">Edit</a>
            <a class="btnDanger btnSmall" href="{url_for('delete_event', event_id=e['id'])}" onclick="return confirm('Delete this event?')">Delete</a>
          </td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        opts = "".join([f"<option>{s}</option>" for s in STATUS_OPTIONS])
        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Event</h3>
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
    else:
        body += "<div class='card'><p class='muted'>Member view only.</p></div>"

    return render(body)


@app.route("/events/<int:event_id>/edit", methods=["GET", "POST"])
def edit_event(event_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not is_admin(user["role"]):
        abort(403)

    rows = db_query(f"SELECT * FROM events WHERE id={_ph()}", (event_id,))
    if not rows:
        flash("Event not found", "error")
        return redirect(url_for("events"))
    e = rows[0]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        date_ = request.form.get("date", "").strip()
        time_ = request.form.get("time", "").strip()
        notes = request.form.get("notes", "").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        status = request.form.get("status", "Pending").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_exec(
            f"UPDATE events SET title={_ph()}, date={_ph()}, time={_ph()}, notes={_ph()}, assigned_to={_ph()}, status={_ph()}, updated_at={_ph()} "
            f"WHERE id={_ph()}",
            (title, date_, time_, notes, assigned_to, status, now, event_id),
        )
        flash("Event updated ✅")
        return redirect(url_for("events"))

    opts = "".join([f"<option {'selected' if s==(e.get('status') or '') else ''}>{s}</option>" for s in STATUS_OPTIONS])

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">✏️ Edit Event</h2>
      <form method="post">
        <label>Title</label>
        <input name="title" value="{e.get('title','')}" required>
        <div class="row">
          <div class="col">
            <label>Date</label>
            <input name="date" type="date" value="{e.get('date','')}" required>
          </div>
          <div class="col">
            <label>Time</label>
            <input name="time" type="time" value="{e.get('time','')}" required>
          </div>
        </div>
        <div class="row">
          <div class="col">
            <label>Assigned To</label>
            <input name="assigned_to" value="{e.get('assigned_to') or ''}">
          </div>
          <div class="col">
            <label>Status</label>
            <select name="status">{opts}</select>
          </div>
        </div>
        <label>Notes</label>
        <textarea name="notes">{e.get('notes') or ''}</textarea>
        <button class="btn" type="submit">Save</button>
        <a class="btn2" href="{url_for('events')}">Cancel</a>
      </form>
    </div>
    """
    return render(body)


@app.route("/events/<int:event_id>/delete")
def delete_event(event_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not can_delete(user["role"]):
        abort(403)

    db_exec(f"DELETE FROM events WHERE id={_ph()}", (event_id,))
    flash("Event deleted 🗑️")
    return redirect(url_for("events"))


# ==========================================================
# GUESTS
# ==========================================================
@app.route("/guests", methods=["GET", "POST"])
def guests():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            flash("Only Admins can add guests.", "error")
            return redirect(url_for("guests"))

        side = request.form.get("side", "Bride").strip()
        name = request.form.get("name", "").strip()
        relation = request.form.get("relation", "").strip()
        phone = request.form.get("phone", "").strip()
        visited = 1 if request.form.get("visited") == "on" else 0
        stay_required = 1 if request.form.get("stay_required") == "on" else 0
        room_no = request.form.get("room_no", "").strip()
        notes = request.form.get("notes", "").strip()

        if not name:
            flash("Guest name is required.", "error")
            return redirect(url_for("guests"))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec(
            f"INSERT INTO guests (side, name, relation, phone, visited, stay_required, room_no, notes, created_by, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
            (side, name, relation, phone, visited, stay_required, room_no, notes, user["name"], now),
        )
        flash("Guest added ✅")
        return redirect(url_for("guests"))

    rows = db_query("SELECT * FROM guests ORDER BY side ASC, name ASC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">👥 Guest List</h2>
      <table>
        <tr>
          <th>Side</th><th>Name</th><th>Relation</th><th>Phone</th>
          <th>Visited</th><th>Stay</th><th>Room</th><th>Notes</th><th class="right">Actions</th>
        </tr>
    """
    for g1 in rows:
        visited = "✅" if safe_int(g1.get("visited", 0)) == 1 else "—"
        stay = "🏨" if safe_int(g1.get("stay_required", 0)) == 1 else "—"
        body += f"""
        <tr>
          <td><span class="tag">{g1.get('side','')}</span></td>
          <td><b>{g1.get('name','')}</b></td>
          <td class="muted">{g1.get('relation') or ''}</td>
          <td class="muted">{g1.get('phone') or ''}</td>
          <td>{visited}</td>
          <td>{stay}</td>
          <td class="muted">{g1.get('room_no') or ''}</td>
          <td class="muted">{(g1.get('notes') or '')[:60]}</td>
          <td class="right actions">
            <a class="btn2 btnSmall" href="{url_for('edit_guest', guest_id=g1['id'])}">Edit</a>
            <a class="btnDanger btnSmall" href="{url_for('delete_guest', guest_id=g1['id'])}" onclick="return confirm('Delete this guest?')">Delete</a>
          </td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        side_opts = "".join([f"<option>{s}</option>" for s in GUEST_SIDE_OPTIONS])
        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Guest</h3>
          <form method="post">
            <div class="row">
              <div class="col">
                <label>Side</label>
                <select name="side">{side_opts}</select>
              </div>
              <div class="col">
                <label>Name</label>
                <input name="name" required>
              </div>
            </div>
            <div class="row">
              <div class="col">
                <label>Relation</label>
                <input name="relation">
              </div>
              <div class="col">
                <label>Phone</label>
                <input name="phone">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label><input type="checkbox" name="visited"> Visited</label>
              </div>
              <div class="col">
                <label><input type="checkbox" name="stay_required"> Stay Required</label>
              </div>
            </div>

            <label>Room No</label>
            <input name="room_no">

            <label>Notes</label>
            <textarea name="notes"></textarea>

            <button class="btn" type="submit">Add Guest</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>Member view only.</p></div>"

    return render(body)


@app.route("/guests/<int:guest_id>/edit", methods=["GET", "POST"])
def edit_guest(guest_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not is_admin(user["role"]):
        abort(403)

    rows = db_query(f"SELECT * FROM guests WHERE id={_ph()}", (guest_id,))
    if not rows:
        flash("Guest not found", "error")
        return redirect(url_for("guests"))
    g1 = rows[0]

    if request.method == "POST":
        side = request.form.get("side", "Bride").strip()
        name = request.form.get("name", "").strip()
        relation = request.form.get("relation", "").strip()
        phone = request.form.get("phone", "").strip()
        visited = 1 if request.form.get("visited") == "on" else 0
        stay_required = 1 if request.form.get("stay_required") == "on" else 0
        room_no = request.form.get("room_no", "").strip()
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_exec(
            f"UPDATE guests SET side={_ph()}, name={_ph()}, relation={_ph()}, phone={_ph()}, visited={_ph()}, stay_required={_ph()}, room_no={_ph()}, notes={_ph()}, updated_at={_ph()} "
            f"WHERE id={_ph()}",
            (side, name, relation, phone, visited, stay_required, room_no, notes, now, guest_id),
        )
        flash("Guest updated ✅")
        return redirect(url_for("guests"))

    side_opts = "".join([f"<option {'selected' if s==(g1.get('side') or '') else ''}>{s}</option>" for s in GUEST_SIDE_OPTIONS])
    checked_visited = "checked" if safe_int(g1.get("visited", 0)) == 1 else ""
    checked_stay = "checked" if safe_int(g1.get("stay_required", 0)) == 1 else ""

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">✏️ Edit Guest</h2>
      <form method="post">
        <div class="row">
          <div class="col">
            <label>Side</label>
            <select name="side">{side_opts}</select>
          </div>
          <div class="col">
            <label>Name</label>
            <input name="name" value="{g1.get('name','')}" required>
          </div>
        </div>

        <div class="row">
          <div class="col">
            <label>Relation</label>
            <input name="relation" value="{g1.get('relation') or ''}">
          </div>
          <div class="col">
            <label>Phone</label>
            <input name="phone" value="{g1.get('phone') or ''}">
          </div>
        </div>

        <div class="row">
          <div class="col">
            <label><input type="checkbox" name="visited" {checked_visited}> Visited</label>
          </div>
          <div class="col">
            <label><input type="checkbox" name="stay_required" {checked_stay}> Stay Required</label>
          </div>
        </div>

        <label>Room No</label>
        <input name="room_no" value="{g1.get('room_no') or ''}">

        <label>Notes</label>
        <textarea name="notes">{g1.get('notes') or ''}</textarea>

        <button class="btn" type="submit">Save</button>
        <a class="btn2" href="{url_for('guests')}">Cancel</a>
      </form>
    </div>
    """
    return render(body)


@app.route("/guests/<int:guest_id>/delete")
def delete_guest(guest_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not can_delete(user["role"]):
        abort(403)

    db_exec(f"DELETE FROM guests WHERE id={_ph()}", (guest_id,))
    flash("Guest deleted 🗑️")
    return redirect(url_for("guests"))


# ==========================================================
# TRAVEL (Guest-wise)
# ==========================================================
@app.route("/travel", methods=["GET", "POST"])
def travel():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    guests = db_query("SELECT id, name, side FROM guests ORDER BY side ASC, name ASC")

    if request.method == "POST":
        if not is_admin(role):
            flash("Only Admins can add travel details.", "error")
            return redirect(url_for("travel"))

        guest_id = safe_int(request.form.get("guest_id", "0"))
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

        if guest_id <= 0:
            flash("Please select a guest.", "error")
            return redirect(url_for("travel"))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec(
            f"INSERT INTO travel (guest_id, arrival_date, arrival_time, mode, ref_no, pickup_required, pickup_person, vehicle, checkin_date, checkout_date, status, assigned_to, notes, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
            (
                guest_id, arrival_date, arrival_time, mode, ref_no,
                pickup_required, pickup_person, vehicle,
                checkin_date, checkout_date,
                status, assigned_to, notes, now
            ),
        )
        flash("Travel details added ✅")
        return redirect(url_for("travel"))

    # join travel + guests
    rows = db_query("""
        SELECT t.*, g.name AS guest_name, g.side AS guest_side
        FROM travel t
        LEFT JOIN guests g ON g.id = t.guest_id
        ORDER BY g.side ASC, g.name ASC, t.id DESC
    """)

    body = """
    <div class="card">
      <h2 style="margin-top:0;">🧳 Travel & Stay (Guest-wise)</h2>
      <table>
        <tr>
          <th>Guest</th><th>Arrival</th><th>Mode/Ref</th><th>Pickup</th>
          <th>Check-in/out</th><th>Status</th><th>Assigned</th><th class="right">Actions</th>
        </tr>
    """
    for t in rows:
        pickup = "✅" if safe_int(t.get("pickup_required", 0)) == 1 else "—"
        body += f"""
        <tr>
          <td><span class="tag">{t.get('guest_side','')}</span> <b>{t.get('guest_name') or ''}</b></td>
          <td class="muted">{t.get('arrival_date') or ''} {t.get('arrival_time') or ''}</td>
          <td class="muted">{t.get('mode') or ''}<br>{t.get('ref_no') or ''}</td>
          <td class="muted">{pickup}<br>{t.get('pickup_person') or ''} {t.get('vehicle') or ''}</td>
          <td class="muted">{t.get('checkin_date') or ''}<br>{t.get('checkout_date') or ''}</td>
          <td><span class="tag">{t.get('status') or ''}</span></td>
          <td class="muted">{t.get('assigned_to') or ''}</td>
          <td class="right actions">
            <a class="btn2 btnSmall" href="{url_for('edit_travel', travel_id=t['id'])}">Edit</a>
            <a class="btnDanger btnSmall" href="{url_for('delete_travel', travel_id=t['id'])}" onclick="return confirm('Delete travel record?')">Delete</a>
          </td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        guest_opts = ""
        for g1 in guests:
            guest_opts += f"<option value='{g1['id']}'>{g1['side']} - {g1['name']}</option>"

        mode_opts = "".join([f"<option>{m}</option>" for m in TRAVEL_MODE_OPTIONS])
        status_opts = "".join([f"<option>{s}</option>" for s in STATUS_OPTIONS])

        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Travel</h3>
          <form method="post">
            <label>Guest</label>
            <select name="guest_id" required>
              <option value="">-- Select Guest --</option>
              {guest_opts}
            </select>

            <div class="grid2">
              <div>
                <label>Arrival Date</label>
                <input name="arrival_date" type="date">
              </div>
              <div>
                <label>Arrival Time</label>
                <input name="arrival_time" type="time">
              </div>
            </div>

            <div class="grid2">
              <div>
                <label>Mode</label>
                <select name="mode">{mode_opts}</select>
              </div>
              <div>
                <label>Ref No (Train/Flight/PNR)</label>
                <input name="ref_no">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label><input type="checkbox" name="pickup_required"> Pickup Required</label>
              </div>
              <div class="col">
                <label>Pickup Person</label>
                <input name="pickup_person">
              </div>
              <div class="col">
                <label>Vehicle</label>
                <input name="vehicle">
              </div>
            </div>

            <div class="grid2">
              <div>
                <label>Check-in Date</label>
                <input name="checkin_date" type="date">
              </div>
              <div>
                <label>Check-out Date</label>
                <input name="checkout_date" type="date">
              </div>
            </div>

            <div class="grid2">
              <div>
                <label>Status</label>
                <select name="status">{status_opts}</select>
              </div>
              <div>
                <label>Assigned To</label>
                <input name="assigned_to" value="Vijay">
              </div>
            </div>

            <label>Notes</label>
            <textarea name="notes"></textarea>

            <button class="btn" type="submit">Add Travel</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>Member view only.</p></div>"

    return render(body)


@app.route("/travel/<int:travel_id>/edit", methods=["GET", "POST"])
def edit_travel(travel_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not is_admin(user["role"]):
        abort(403)

    guests = db_query("SELECT id, name, side FROM guests ORDER BY side ASC, name ASC")
    rows = db_query(f"SELECT * FROM travel WHERE id={_ph()}", (travel_id,))
    if not rows:
        flash("Travel record not found", "error")
        return redirect(url_for("travel"))
    t = rows[0]

    if request.method == "POST":
        guest_id = safe_int(request.form.get("guest_id", "0"))
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

        db_exec(
            f"UPDATE travel SET guest_id={_ph()}, arrival_date={_ph()}, arrival_time={_ph()}, mode={_ph()}, ref_no={_ph()}, "
            f"pickup_required={_ph()}, pickup_person={_ph()}, vehicle={_ph()}, checkin_date={_ph()}, checkout_date={_ph()}, "
            f"status={_ph()}, assigned_to={_ph()}, notes={_ph()}, updated_at={_ph()} WHERE id={_ph()}",
            (
                guest_id, arrival_date, arrival_time, mode, ref_no,
                pickup_required, pickup_person, vehicle,
                checkin_date, checkout_date,
                status, assigned_to, notes, now, travel_id
            ),
        )
        flash("Travel updated ✅")
        return redirect(url_for("travel"))

    guest_opts = ""
    for g1 in guests:
        sel = "selected" if safe_int(t.get("guest_id", 0)) == safe_int(g1["id"], 0) else ""
        guest_opts += f"<option value='{g1['id']}' {sel}>{g1['side']} - {g1['name']}</option>"

    mode_opts = "".join([f"<option {'selected' if m==(t.get('mode') or '') else ''}>{m}</option>" for m in TRAVEL_MODE_OPTIONS])
    status_opts = "".join([f"<option {'selected' if s==(t.get('status') or '') else ''}>{s}</option>" for s in STATUS_OPTIONS])
    checked_pickup = "checked" if safe_int(t.get("pickup_required", 0)) == 1 else ""

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">✏️ Edit Travel</h2>
      <form method="post">
        <label>Guest</label>
        <select name="guest_id" required>{guest_opts}</select>

        <div class="grid2">
          <div>
            <label>Arrival Date</label>
            <input name="arrival_date" type="date" value="{t.get('arrival_date') or ''}">
          </div>
          <div>
            <label>Arrival Time</label>
            <input name="arrival_time" type="time" value="{t.get('arrival_time') or ''}">
          </div>
        </div>

        <div class="grid2">
          <div>
            <label>Mode</label>
            <select name="mode">{mode_opts}</select>
          </div>
          <div>
            <label>Ref No</label>
            <input name="ref_no" value="{t.get('ref_no') or ''}">
          </div>
        </div>

        <div class="row">
          <div class="col">
            <label><input type="checkbox" name="pickup_required" {checked_pickup}> Pickup Required</label>
          </div>
          <div class="col">
            <label>Pickup Person</label>
            <input name="pickup_person" value="{t.get('pickup_person') or ''}">
          </div>
          <div class="col">
            <label>Vehicle</label>
            <input name="vehicle" value="{t.get('vehicle') or ''}">
          </div>
        </div>

        <div class="grid2">
          <div>
            <label>Check-in Date</label>
            <input name="checkin_date" type="date" value="{t.get('checkin_date') or ''}">
          </div>
          <div>
            <label>Check-out Date</label>
            <input name="checkout_date" type="date" value="{t.get('checkout_date') or ''}">
          </div>
        </div>

        <div class="grid2">
          <div>
            <label>Status</label>
            <select name="status">{status_opts}</select>
          </div>
          <div>
            <label>Assigned To</label>
            <input name="assigned_to" value="{t.get('assigned_to') or ''}">
          </div>
        </div>

        <label>Notes</label>
        <textarea name="notes">{t.get('notes') or ''}</textarea>

        <button class="btn" type="submit">Save</button>
        <a class="btn2" href="{url_for('travel')}">Cancel</a>
      </form>
    </div>
    """
    return render(body)


@app.route("/travel/<int:travel_id>/delete")
def delete_travel(travel_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not can_delete(user["role"]):
        abort(403)

    db_exec(f"DELETE FROM travel WHERE id={_ph()}", (travel_id,))
    flash("Travel deleted 🗑️")
    return redirect(url_for("travel"))


# ==========================================================
# VENDORS
# ==========================================================
@app.route("/vendors", methods=["GET", "POST"])
def vendors():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            flash("Only Admins can add vendors.", "error")
            return redirect(url_for("vendors"))

        category = request.form.get("category", "").strip()
        vendor_name = request.form.get("vendor_name", "").strip()
        contact_person = request.form.get("contact_person", "").strip()
        phone = request.form.get("phone", "").strip()
        status = request.form.get("status", "Pending").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not category:
            flash("Category is required.", "error")
            return redirect(url_for("vendors"))

        db_exec(
            f"INSERT INTO vendors (category, vendor_name, contact_person, phone, status, assigned_to, notes, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
            (category, vendor_name, contact_person, phone, status, assigned_to, notes, now),
        )
        flash("Vendor added ✅")
        return redirect(url_for("vendors"))

    rows = db_query("SELECT * FROM vendors ORDER BY category ASC, vendor_name ASC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">🧑‍🔧 Vendors</h2>
      <table>
        <tr>
          <th>Category</th><th>Vendor</th><th>Contact</th><th>Phone</th>
          <th>Status</th><th>Assigned</th><th>Notes</th><th class="right">Actions</th>
        </tr>
    """
    for v in rows:
        body += f"""
        <tr>
          <td><span class="tag">{v.get('category','')}</span></td>
          <td><b>{v.get('vendor_name') or ''}</b></td>
          <td class="muted">{v.get('contact_person') or ''}</td>
          <td class="muted">{v.get('phone') or ''}</td>
          <td><span class="tag">{v.get('status') or ''}</span></td>
          <td class="muted">{v.get('assigned_to') or ''}</td>
          <td class="muted">{(v.get('notes') or '')[:60]}</td>
          <td class="right actions">
            <a class="btn2 btnSmall" href="{url_for('edit_vendor', vendor_id=v['id'])}">Edit</a>
            <a class="btnDanger btnSmall" href="{url_for('delete_vendor', vendor_id=v['id'])}" onclick="return confirm('Delete this vendor?')">Delete</a>
          </td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        cat_opts = "".join([f"<option>{c}</option>" for c in VENDOR_CATEGORIES])
        status_opts = "".join([f"<option>{s}</option>" for s in STATUS_OPTIONS])

        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Vendor</h3>
          <form method="post">
            <label>Category</label>
            <select name="category">{cat_opts}</select>

            <div class="row">
              <div class="col">
                <label>Vendor Name</label>
                <input name="vendor_name">
              </div>
              <div class="col">
                <label>Contact Person</label>
                <input name="contact_person">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label>Phone</label>
                <input name="phone">
              </div>
              <div class="col">
                <label>Status</label>
                <select name="status">{status_opts}</select>
              </div>
            </div>

            <label>Assigned To</label>
            <input name="assigned_to" value="Vijay">

            <label>Notes</label>
            <textarea name="notes"></textarea>

            <button class="btn" type="submit">Add Vendor</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>Member view only.</p></div>"

    return render(body)


@app.route("/vendors/<int:vendor_id>/edit", methods=["GET", "POST"])
def edit_vendor(vendor_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not is_admin(user["role"]):
        abort(403)

    rows = db_query(f"SELECT * FROM vendors WHERE id={_ph()}", (vendor_id,))
    if not rows:
        flash("Vendor not found", "error")
        return redirect(url_for("vendors"))
    v = rows[0]

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        vendor_name = request.form.get("vendor_name", "").strip()
        contact_person = request.form.get("contact_person", "").strip()
        phone = request.form.get("phone", "").strip()
        status = request.form.get("status", "Pending").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_exec(
            f"UPDATE vendors SET category={_ph()}, vendor_name={_ph()}, contact_person={_ph()}, phone={_ph()}, status={_ph()}, assigned_to={_ph()}, notes={_ph()}, updated_at={_ph()} "
            f"WHERE id={_ph()}",
            (category, vendor_name, contact_person, phone, status, assigned_to, notes, now, vendor_id),
        )
        flash("Vendor updated ✅")
        return redirect(url_for("vendors"))

    cat_opts = "".join([f"<option {'selected' if c==(v.get('category') or '') else ''}>{c}</option>" for c in VENDOR_CATEGORIES])
    status_opts = "".join([f"<option {'selected' if s==(v.get('status') or '') else ''}>{s}</option>" for s in STATUS_OPTIONS])

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">✏️ Edit Vendor</h2>
      <form method="post">
        <label>Category</label>
        <select name="category">{cat_opts}</select>

        <div class="row">
          <div class="col">
            <label>Vendor Name</label>
            <input name="vendor_name" value="{v.get('vendor_name') or ''}">
          </div>
          <div class="col">
            <label>Contact Person</label>
            <input name="contact_person" value="{v.get('contact_person') or ''}">
          </div>
        </div>

        <div class="row">
          <div class="col">
            <label>Phone</label>
            <input name="phone" value="{v.get('phone') or ''}">
          </div>
          <div class="col">
            <label>Status</label>
            <select name="status">{status_opts}</select>
          </div>
        </div>

        <label>Assigned To</label>
        <input name="assigned_to" value="{v.get('assigned_to') or ''}">

        <label>Notes</label>
        <textarea name="notes">{v.get('notes') or ''}</textarea>

        <button class="btn" type="submit">Save</button>
        <a class="btn2" href="{url_for('vendors')}">Cancel</a>
      </form>
    </div>
    """
    return render(body)


@app.route("/vendors/<int:vendor_id>/delete")
def delete_vendor(vendor_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not can_delete(user["role"]):
        abort(403)

    db_exec(f"DELETE FROM vendors WHERE id={_ph()}", (vendor_id,))
    flash("Vendor deleted 🗑️")
    return redirect(url_for("vendors"))


# ==========================================================
# VENUE / ROOMS
# ==========================================================
@app.route("/venue_rooms", methods=["GET", "POST"])
def venue_rooms():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            flash("Only Admins can add room entries.", "error")
            return redirect(url_for("venue_rooms"))

        room_no = request.form.get("room_no", "").strip()
        guest_name = request.form.get("guest_name", "").strip()
        checkin = request.form.get("checkin", "").strip()
        checkout = request.form.get("checkout", "").strip()
        status = request.form.get("status", "Pending").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_exec(
            f"INSERT INTO venue_rooms (room_no, guest_name, checkin, checkout, status, assigned_to, notes, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
            (room_no, guest_name, checkin, checkout, status, assigned_to, notes, now),
        )
        flash("Room entry added ✅")
        return redirect(url_for("venue_rooms"))

    rows = db_query("SELECT * FROM venue_rooms ORDER BY room_no ASC, guest_name ASC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">🏨 Venue / Rooms</h2>
      <table>
        <tr>
          <th>Room</th><th>Guest</th><th>Check-in</th><th>Check-out</th>
          <th>Status</th><th>Assigned</th><th>Notes</th><th class="right">Actions</th>
        </tr>
    """
    for r1 in rows:
        body += f"""
        <tr>
          <td><b>{r1.get('room_no') or ''}</b></td>
          <td>{r1.get('guest_name') or ''}</td>
          <td class="muted">{r1.get('checkin') or ''}</td>
          <td class="muted">{r1.get('checkout') or ''}</td>
          <td><span class="tag">{r1.get('status') or ''}</span></td>
          <td class="muted">{r1.get('assigned_to') or ''}</td>
          <td class="muted">{(r1.get('notes') or '')[:60]}</td>
          <td class="right actions">
            <a class="btn2 btnSmall" href="{url_for('edit_room', room_id=r1['id'])}">Edit</a>
            <a class="btnDanger btnSmall" href="{url_for('delete_room', room_id=r1['id'])}" onclick="return confirm('Delete this room entry?')">Delete</a>
          </td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        status_opts = "".join([f"<option>{s}</option>" for s in STATUS_OPTIONS])
        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Room Entry</h3>
          <form method="post">
            <div class="row">
              <div class="col">
                <label>Room No</label>
                <input name="room_no">
              </div>
              <div class="col">
                <label>Guest Name</label>
                <input name="guest_name">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label>Check-in</label>
                <input name="checkin" placeholder="2026-02-18 12:00">
              </div>
              <div class="col">
                <label>Check-out</label>
                <input name="checkout" placeholder="2026-02-21 10:00">
              </div>
            </div>

            <div class="row">
              <div class="col">
                <label>Status</label>
                <select name="status">{status_opts}</select>
              </div>
              <div class="col">
                <label>Assigned To</label>
                <input name="assigned_to" value="Vijay">
              </div>
            </div>

            <label>Notes</label>
            <textarea name="notes"></textarea>

            <button class="btn" type="submit">Add Room Entry</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>Member view only.</p></div>"

    return render(body)


@app.route("/venue_rooms/<int:room_id>/edit", methods=["GET", "POST"])
def edit_room(room_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not is_admin(user["role"]):
        abort(403)

    rows = db_query(f"SELECT * FROM venue_rooms WHERE id={_ph()}", (room_id,))
    if not rows:
        flash("Room entry not found", "error")
        return redirect(url_for("venue_rooms"))
    r1 = rows[0]

    if request.method == "POST":
        room_no = request.form.get("room_no", "").strip()
        guest_name = request.form.get("guest_name", "").strip()
        checkin = request.form.get("checkin", "").strip()
        checkout = request.form.get("checkout", "").strip()
        status = request.form.get("status", "Pending").strip()
        assigned_to = request.form.get("assigned_to", "").strip()
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_exec(
            f"UPDATE venue_rooms SET room_no={_ph()}, guest_name={_ph()}, checkin={_ph()}, checkout={_ph()}, status={_ph()}, assigned_to={_ph()}, notes={_ph()}, updated_at={_ph()} "
            f"WHERE id={_ph()}",
            (room_no, guest_name, checkin, checkout, status, assigned_to, notes, now, room_id),
        )
        flash("Room entry updated ✅")
        return redirect(url_for("venue_rooms"))

    status_opts = "".join([f"<option {'selected' if s==(r1.get('status') or '') else ''}>{s}</option>" for s in STATUS_OPTIONS])

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">✏️ Edit Room Entry</h2>
      <form method="post">
        <div class="row">
          <div class="col">
            <label>Room No</label>
            <input name="room_no" value="{r1.get('room_no') or ''}">
          </div>
          <div class="col">
            <label>Guest Name</label>
            <input name="guest_name" value="{r1.get('guest_name') or ''}">
          </div>
        </div>

        <div class="row">
          <div class="col">
            <label>Check-in</label>
            <input name="checkin" value="{r1.get('checkin') or ''}">
          </div>
          <div class="col">
            <label>Check-out</label>
            <input name="checkout" value="{r1.get('checkout') or ''}">
          </div>
        </div>

        <div class="row">
          <div class="col">
            <label>Status</label>
            <select name="status">{status_opts}</select>
          </div>
          <div class="col">
            <label>Assigned To</label>
            <input name="assigned_to" value="{r1.get('assigned_to') or ''}">
          </div>
        </div>

        <label>Notes</label>
        <textarea name="notes">{r1.get('notes') or ''}</textarea>

        <button class="btn" type="submit">Save</button>
        <a class="btn2" href="{url_for('venue_rooms')}">Cancel</a>
      </form>
    </div>
    """
    return render(body)


@app.route("/venue_rooms/<int:room_id>/delete")
def delete_room(room_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not can_delete(user["role"]):
        abort(403)

    db_exec(f"DELETE FROM venue_rooms WHERE id={_ph()}", (room_id,))
    flash("Room entry deleted 🗑️")
    return redirect(url_for("venue_rooms"))


# ==========================================================
# NOTES
# ==========================================================
@app.route("/notes", methods=["GET", "POST"])
def notes():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            flash("Only Admins can add notes.", "error")
            return redirect(url_for("notes"))

        category = request.form.get("category", "General").strip()
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title:
            flash("Note title required.", "error")
            return redirect(url_for("notes"))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec(
            f"INSERT INTO notes (category, title, content, created_by, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
            (category, title, content, user["name"], now),
        )
        flash("Note added ✅")
        return redirect(url_for("notes"))

    rows = db_query("SELECT * FROM notes ORDER BY id DESC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">📝 Notes</h2>
      <table>
        <tr><th>Category</th><th>Title</th><th>Content</th><th>By</th><th class="right">Actions</th></tr>
    """
    for n in rows:
        body += f"""
        <tr>
          <td><span class="tag">{n.get('category') or ''}</span></td>
          <td><b>{n.get('title') or ''}</b></td>
          <td class="muted">{(n.get('content') or '')[:120]}</td>
          <td class="muted">{n.get('created_by') or ''}</td>
          <td class="right actions">
            <a class="btn2 btnSmall" href="{url_for('edit_note', note_id=n['id'])}">Edit</a>
            <a class="btnDanger btnSmall" href="{url_for('delete_note', note_id=n['id'])}" onclick="return confirm('Delete this note?')">Delete</a>
          </td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        cat_opts = "".join([f"<option>{c}</option>" for c in NOTE_CATEGORIES])
        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Note</h3>
          <form method="post">
            <label>Category</label>
            <select name="category">{cat_opts}</select>

            <label>Title</label>
            <input name="title" required>

            <label>Content</label>
            <textarea name="content" required></textarea>

            <button class="btn" type="submit">Add Note</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>Member can view notes.</p></div>"

    return render(body)


@app.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
def edit_note(note_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not is_admin(user["role"]):
        abort(403)

    rows = db_query(f"SELECT * FROM notes WHERE id={_ph()}", (note_id,))
    if not rows:
        flash("Note not found", "error")
        return redirect(url_for("notes"))
    n = rows[0]

    if request.method == "POST":
        category = request.form.get("category", "General").strip()
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_exec(
            f"UPDATE notes SET category={_ph()}, title={_ph()}, content={_ph()}, updated_at={_ph()} WHERE id={_ph()}",
            (category, title, content, now, note_id),
        )
        flash("Note updated ✅")
        return redirect(url_for("notes"))

    cat_opts = "".join([f"<option {'selected' if c==(n.get('category') or '') else ''}>{c}</option>" for c in NOTE_CATEGORIES])

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">✏️ Edit Note</h2>
      <form method="post">
        <label>Category</label>
        <select name="category">{cat_opts}</select>

        <label>Title</label>
        <input name="title" value="{n.get('title') or ''}" required>

        <label>Content</label>
        <textarea name="content" required>{n.get('content') or ''}</textarea>

        <button class="btn" type="submit">Save</button>
        <a class="btn2" href="{url_for('notes')}">Cancel</a>
      </form>
    </div>
    """
    return render(body)


@app.route("/notes/<int:note_id>/delete")
def delete_note(note_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not can_delete(user["role"]):
        abort(403)

    db_exec(f"DELETE FROM notes WHERE id={_ph()}", (note_id,))
    flash("Note deleted 🗑️")
    return redirect(url_for("notes"))


# ==========================================================
# UPLOADS (Google Drive links)
# ==========================================================
@app.route("/uploads", methods=["GET", "POST"])
def uploads():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            flash("Only Admins can add uploads.", "error")
            return redirect(url_for("uploads"))

        category = request.form.get("category", "Receipt").strip()
        title = request.form.get("title", "").strip()
        drive_link = request.form.get("drive_link", "").strip()
        notes = request.form.get("notes", "").strip()

        if not title or not drive_link:
            flash("Title and Google Drive link are required.", "error")
            return redirect(url_for("uploads"))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec(
            f"INSERT INTO uploads (category, title, drive_link, notes, uploaded_by, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
            (category, title, drive_link, notes, user["name"], now),
        )
        flash("Upload link saved ✅")
        return redirect(url_for("uploads"))

    rows = db_query("SELECT * FROM uploads ORDER BY id DESC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">📎 Uploads (Google Drive Links)</h2>
      <p class="muted">
        Upload your receipt/photo to Google Drive → Copy share link → paste here.
      </p>
      <table>
        <tr><th>Category</th><th>Title</th><th>Drive Link</th><th>Notes</th><th>By</th><th class="right">Actions</th></tr>
    """
    for u in rows:
        link = u.get("drive_link") or ""
        body += f"""
        <tr>
          <td><span class="tag">{u.get('category') or ''}</span></td>
          <td><b>{u.get('title') or ''}</b></td>
          <td><a href="{link}" target="_blank">Open</a></td>
          <td class="muted">{(u.get('notes') or '')[:80]}</td>
          <td class="muted">{u.get('uploaded_by') or ''}</td>
          <td class="right actions">
            <a class="btn2 btnSmall" href="{url_for('edit_upload', upload_id=u['id'])}">Edit</a>
            <a class="btnDanger btnSmall" href="{url_for('delete_upload', upload_id=u['id'])}" onclick="return confirm('Delete this upload?')">Delete</a>
          </td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        cat_opts = "".join([f"<option>{c}</option>" for c in UPLOAD_CATEGORIES])
        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Upload Link</h3>
          <form method="post">
            <label>Category</label>
            <select name="category">{cat_opts}</select>

            <label>Title</label>
            <input name="title" required>

            <label>Google Drive Share Link</label>
            <input name="drive_link" placeholder="https://drive.google.com/..." required>

            <label>Notes</label>
            <textarea name="notes"></textarea>

            <button class="btn" type="submit">Save Link</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>Members can view uploads.</p></div>"

    return render(body)


@app.route("/uploads/<int:upload_id>/edit", methods=["GET", "POST"])
def edit_upload(upload_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not is_admin(user["role"]):
        abort(403)

    rows = db_query(f"SELECT * FROM uploads WHERE id={_ph()}", (upload_id,))
    if not rows:
        flash("Upload not found", "error")
        return redirect(url_for("uploads"))
    u = rows[0]

    if request.method == "POST":
        category = request.form.get("category", "Receipt").strip()
        title = request.form.get("title", "").strip()
        drive_link = request.form.get("drive_link", "").strip()
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_exec(
            f"UPDATE uploads SET category={_ph()}, title={_ph()}, drive_link={_ph()}, notes={_ph()}, updated_at={_ph()} WHERE id={_ph()}",
            (category, title, drive_link, notes, now, upload_id),
        )
        flash("Upload updated ✅")
        return redirect(url_for("uploads"))

    cat_opts = "".join([f"<option {'selected' if c==(u.get('category') or '') else ''}>{c}</option>" for c in UPLOAD_CATEGORIES])

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">✏️ Edit Upload</h2>
      <form method="post">
        <label>Category</label>
        <select name="category">{cat_opts}</select>

        <label>Title</label>
        <input name="title" value="{u.get('title') or ''}" required>

        <label>Google Drive Share Link</label>
        <input name="drive_link" value="{u.get('drive_link') or ''}" required>

        <label>Notes</label>
        <textarea name="notes">{u.get('notes') or ''}</textarea>

        <button class="btn" type="submit">Save</button>
        <a class="btn2" href="{url_for('uploads')}">Cancel</a>
      </form>
    </div>
    """
    return render(body)


@app.route("/uploads/<int:upload_id>/delete")
def delete_upload(upload_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not can_delete(user["role"]):
        abort(403)

    db_exec(f"DELETE FROM uploads WHERE id={_ph()}", (upload_id,))
    flash("Upload deleted 🗑️")
    return redirect(url_for("uploads"))


# ==========================================================
# PURCHASES (Admins only, hidden for Members)
# ==========================================================
@app.route("/purchases", methods=["GET", "POST"])
def purchases():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if role == "MEMBER":
        abort(403)

    if request.method == "POST":
        if not is_admin(role):
            abort(403)

        category = request.form.get("category", "").strip()
        item = request.form.get("item", "").strip()
        amount = float(request.form.get("amount", "0") or 0)
        status = request.form.get("status", "Pending").strip()
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not category or not item:
            flash("Category and Item required.", "error")
            return redirect(url_for("purchases"))

        db_exec(
            f"INSERT INTO purchases (category, item, amount, status, notes, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
            (category, item, amount, status, notes, now),
        )
        flash("Purchase added ✅")
        return redirect(url_for("purchases"))

    rows = db_query("SELECT * FROM purchases ORDER BY id DESC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">🛒 Purchases (Admins)</h2>
      <table>
        <tr><th>Category</th><th>Item</th><th>Amount</th><th>Status</th><th>Notes</th><th class="right">Actions</th></tr>
    """
    for p in rows:
        body += f"""
        <tr>
          <td><span class="tag">{p.get('category') or ''}</span></td>
          <td><b>{p.get('item') or ''}</b></td>
          <td>₹ {p.get('amount') or 0}</td>
          <td><span class="tag">{p.get('status') or ''}</span></td>
          <td class="muted">{(p.get('notes') or '')[:70]}</td>
          <td class="right actions">
            <a class="btn2 btnSmall" href="{url_for('edit_purchase', purchase_id=p['id'])}">Edit</a>
            <a class="btnDanger btnSmall" href="{url_for('delete_purchase', purchase_id=p['id'])}" onclick="return confirm('Delete purchase?')">Delete</a>
          </td>
        </tr>
        """
    body += "</table></div>"

    if is_admin(role):
        status_opts = "".join([f"<option>{s}</option>" for s in STATUS_OPTIONS])
        body += f"""
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Purchase</h3>
          <form method="post">
            <label>Category</label>
            <input name="category" placeholder="Clothes / Jewellery / Puja / etc" required>

            <label>Item</label>
            <input name="item" required>

            <label>Amount (₹)</label>
            <input name="amount" type="number" step="0.01" value="0">

            <label>Status</label>
            <select name="status">{status_opts}</select>

            <label>Notes</label>
            <textarea name="notes"></textarea>

            <button class="btn" type="submit">Add Purchase</button>
          </form>
        </div>
        """
    return render(body)


@app.route("/purchases/<int:purchase_id>/edit", methods=["GET", "POST"])
def edit_purchase(purchase_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if user["role"] == "MEMBER":
        abort(403)

    rows = db_query(f"SELECT * FROM purchases WHERE id={_ph()}", (purchase_id,))
    if not rows:
        flash("Purchase not found", "error")
        return redirect(url_for("purchases"))
    p = rows[0]

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        item = request.form.get("item", "").strip()
        amount = float(request.form.get("amount", "0") or 0)
        status = request.form.get("status", "Pending").strip()
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_exec(
            f"UPDATE purchases SET category={_ph()}, item={_ph()}, amount={_ph()}, status={_ph()}, notes={_ph()}, updated_at={_ph()} WHERE id={_ph()}",
            (category, item, amount, status, notes, now, purchase_id),
        )
        flash("Purchase updated ✅")
        return redirect(url_for("purchases"))

    status_opts = "".join([f"<option {'selected' if s==(p.get('status') or '') else ''}>{s}</option>" for s in STATUS_OPTIONS])

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">✏️ Edit Purchase</h2>
      <form method="post">
        <label>Category</label>
        <input name="category" value="{p.get('category') or ''}" required>

        <label>Item</label>
        <input name="item" value="{p.get('item') or ''}" required>

        <label>Amount (₹)</label>
        <input name="amount" type="number" step="0.01" value="{p.get('amount') or 0}">

        <label>Status</label>
        <select name="status">{status_opts}</select>

        <label>Notes</label>
        <textarea name="notes">{p.get('notes') or ''}</textarea>

        <button class="btn" type="submit">Save</button>
        <a class="btn2" href="{url_for('purchases')}">Cancel</a>
      </form>
    </div>
    """
    return render(body)


@app.route("/purchases/<int:purchase_id>/delete")
def delete_purchase(purchase_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if not can_delete(user["role"]):
        abort(403)

    db_exec(f"DELETE FROM purchases WHERE id={_ph()}", (purchase_id,))
    flash("Purchase deleted 🗑️")
    return redirect(url_for("purchases"))


# ==========================================================
# COMMERCIALS (Super Admin only)
# ==========================================================
@app.route("/commercials", methods=["GET", "POST"])
def commercials():
    r = require_login()
    if r:
        return r

    user = current_user()
    if user["role"] != "SUPER_ADMIN":
        abort(403)

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        amount = float(request.form.get("amount", "0") or 0)
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not category:
            flash("Category required.", "error")
            return redirect(url_for("commercials"))

        db_exec(
            f"INSERT INTO commercials (category, amount, notes, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()})",
            (category, amount, notes, now),
        )
        flash("Commercial added ✅")
        return redirect(url_for("commercials"))

    rows = db_query("SELECT * FROM commercials ORDER BY id DESC")

    body = """
    <div class="card">
      <h2 style="margin-top:0;">💰 Commercials (Super Admin Only)</h2>
      <table>
        <tr><th>Category</th><th>Amount</th><th>Notes</th><th class="right">Actions</th></tr>
    """
    total = 0.0
    for c in rows:
        amt = float(c.get("amount") or 0)
        total += amt
        body += f"""
        <tr>
          <td><span class="tag">{c.get('category') or ''}</span></td>
          <td>₹ {amt}</td>
          <td class="muted">{(c.get('notes') or '')[:90]}</td>
          <td class="right actions">
            <a class="btn2 btnSmall" href="{url_for('edit_commercial', commercial_id=c['id'])}">Edit</a>
            <a class="btnDanger btnSmall" href="{url_for('delete_commercial', commercial_id=c['id'])}" onclick="return confirm('Delete commercial?')">Delete</a>
          </td>
        </tr>
        """
    body += f"</table><div style='margin-top:10px;'><b>Total: ₹ {total}</b></div></div>"

    body += f"""
    <div class="card">
      <h3 style="margin-top:0;">➕ Add Commercial</h3>
      <form method="post">
        <label>Category</label>
        <input name="category" required>

        <label>Amount (₹)</label>
        <input name="amount" type="number" step="0.01" required>

        <label>Notes</label>
        <textarea name="notes"></textarea>

        <button class="btn" type="submit">Add Commercial</button>
      </form>
    </div>
    """
    return render(body)


@app.route("/commercials/<int:commercial_id>/edit", methods=["GET", "POST"])
def edit_commercial(commercial_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if user["role"] != "SUPER_ADMIN":
        abort(403)

    rows = db_query(f"SELECT * FROM commercials WHERE id={_ph()}", (commercial_id,))
    if not rows:
        flash("Commercial not found", "error")
        return redirect(url_for("commercials"))
    c = rows[0]

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        amount = float(request.form.get("amount", "0") or 0)
        notes = request.form.get("notes", "").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_exec(
            f"UPDATE commercials SET category={_ph()}, amount={_ph()}, notes={_ph()}, updated_at={_ph()} WHERE id={_ph()}",
            (category, amount, notes, now, commercial_id),
        )
        flash("Commercial updated ✅")
        return redirect(url_for("commercials"))

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">✏️ Edit Commercial</h2>
      <form method="post">
        <label>Category</label>
        <input name="category" value="{c.get('category') or ''}" required>

        <label>Amount (₹)</label>
        <input name="amount" type="number" step="0.01" value="{c.get('amount') or 0}" required>

        <label>Notes</label>
        <textarea name="notes">{c.get('notes') or ''}</textarea>

        <button class="btn" type="submit">Save</button>
        <a class="btn2" href="{url_for('commercials')}">Cancel</a>
      </form>
    </div>
    """
    return render(body)


@app.route("/commercials/<int:commercial_id>/delete")
def delete_commercial(commercial_id):
    r = require_login()
    if r:
        return r

    user = current_user()
    if user["role"] != "SUPER_ADMIN":
        abort(403)

    db_exec(f"DELETE FROM commercials WHERE id={_ph()}", (commercial_id,))
    flash("Commercial deleted 🗑️")
    return redirect(url_for("commercials"))


# ----------------------------------------------------------
# Errors
# ----------------------------------------------------------
@app.errorhandler(403)
def forbidden(e):
    return render("<div class='card'><h2>403 Forbidden</h2><p class='danger'>You do not have access to this section.</p></div>"), 403


@app.errorhandler(404)
def not_found(e):
    return render("<div class='card'><h2>404 Not Found</h2><p class='muted'>Page not found.</p></div>"), 404


# ----------------------------------------------------------
# Main
# ----------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

