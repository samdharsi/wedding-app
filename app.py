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

HIDE_FOR_MEMBERS = {"purchases", "commercials"}  # future modules


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
    .wrap{ padding:16px; max-width:1200px; margin:auto; }
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
        <a href="{{url_for('vendors')}}">Vendors</a>
        <a href="{{url_for('venue_rooms')}}">Venue/Rooms</a>
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
    # placeholder style
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


def init_db():
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

    # seed events
    existing = db_query("SELECT id FROM events LIMIT 1")
    if len(existing) == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_exec(
            f"INSERT INTO events (title, date, time, notes, assigned_to, status, created_by, updated_at) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
            ("Venue Finalisation", "2026-01-25", "11:00", "Finalize venue and booking confirmation.", "Vijay", "Pending", "SYSTEM", now),
        )

    # seed vendors
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
    # As per your choice: B) Bride/Groom Admin can delete too
    return role in ("SUPER_ADMIN", "BRIDE_ADMIN", "GROOM_ADMIN")


def render(body_html):
    user = current_user()
    role_label = ROLE_LABELS.get(user["role"], "") if user else ""
    return render_template_string(BASE_HTML, title=APP_TITLE, body=body_html, user=user, role_label=role_label)


def safe_int(v, default=0):
    try:
        return int(v)
    except:
        return default


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
            🧑‍🔧 Vendors: <b>{_get_count(vendors_count)}</b><br>
            🏨 Rooms: <b>{_get_count(rooms_count)}</b>
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
# EVENTS (Add / Edit / Delete)
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
# GUESTS (Add / Edit / Delete)
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
# VENDORS (Edit / Delete)
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
# VENUE / ROOMS (Add / Edit / Delete)
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
