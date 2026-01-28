import os
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

STATUS_OPTIONS = ["Pending", "In Progress", "Done"]
GUEST_SIDE_OPTIONS = ["Bride", "Groom"]

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

# ----------------------------------------------------------
# HTML BASE
# ----------------------------------------------------------
BASE_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}}</title>
<style>
body{font-family:Arial;background:#fffaf0;margin:0}
header{background:#b8860b;color:#fff;padding:14px}
.wrap{padding:16px;max-width:1200px;margin:auto}
.card{background:#fff;border-radius:12px;padding:14px;margin-bottom:14px}
.btn{background:#b8860b;color:#fff;padding:8px 14px;border:none;border-radius:8px}
.btn2{border:1px solid #b8860b;padding:8px 14px;border-radius:8px}
.btnDanger{background:#b00020;color:#fff;padding:6px 10px;border-radius:8px}
table{width:100%;border-collapse:collapse}
td,th{border-bottom:1px solid #eee;padding:8px}
.tag{background:#f7e7b6;padding:4px 8px;border-radius:8px}
nav a{color:#fff;margin-right:10px;text-decoration:none}
</style>
</head>
<body>
<header>
<b>{{title}}</b>
{% if user %}
<div>{{user["name"]}} ({{role_label}}) |
<a href="{{url_for('logout')}}" style="color:#fff">Logout</a></div>
<nav>
<a href="/">Home</a>
<a href="/events">Events</a>
<a href="/guests">Guests</a>
<a href="/vendors">Vendors</a>
<a href="/venue_rooms">Venue</a>
<a href="/purchases">Purchases</a>
</nav>
{% endif %}
</header>
<div class="wrap">
{{body|safe}}
</div>
</body>
</html>
"""

# ----------------------------------------------------------
# DB (PostgreSQL via psycopg3)
# ----------------------------------------------------------
def get_db():
    if "db" not in g:
        import psycopg
        g.db = psycopg.connect(DATABASE_URL)
        g.db.autocommit = True
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()

def db_exec(sql, params=()):
    cur = get_db().cursor()
    cur.execute(sql, params)

def db_query(sql, params=()):
    cur = get_db().cursor()
    cur.execute(sql, params)
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

# ----------------------------------------------------------
# INIT DB
# ----------------------------------------------------------
@app.before_request
def init_db():
    db_exec("""
    CREATE TABLE IF NOT EXISTS events(
      id SERIAL PRIMARY KEY,
      title TEXT,date TEXT,time TEXT,
      status TEXT,notes TEXT)
    """)
    db_exec("""
    CREATE TABLE IF NOT EXISTS guests(
      id SERIAL PRIMARY KEY,
      side TEXT,name TEXT,phone TEXT,
      stay INTEGER,notes TEXT)
    """)
    db_exec("""
    CREATE TABLE IF NOT EXISTS vendors(
      id SERIAL PRIMARY KEY,
      category TEXT,name TEXT,phone TEXT,status TEXT)
    """)
    db_exec("""
    CREATE TABLE IF NOT EXISTS venue_rooms(
      id SERIAL PRIMARY KEY,
      room_no TEXT,guest TEXT,notes TEXT)
    """)
    db_exec("""
    CREATE TABLE IF NOT EXISTS purchases(
      id SERIAL PRIMARY KEY,
      item TEXT,amount REAL,
      paid_by TEXT,notes TEXT)
    """)

# ----------------------------------------------------------
# AUTH
# ----------------------------------------------------------
def current_user():
    return USERS.get(session.get("user"))

def require_login():
    if not current_user():
        return redirect("/login")

# ----------------------------------------------------------
# ROUTES
# ----------------------------------------------------------
@app.route("/")
def home():
    if require_login(): return require_login()
    return render("<div class='card'>Welcome</div>")

def render(body):
    u = current_user()
    return render_template_string(
        BASE_HTML,
        title=APP_TITLE,
        body=body,
        user=u,
        role_label=ROLE_LABELS[u["role"]] if u else ""
    )

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["u"].lower()
        p=request.form["p"]
        if u in USERS and USERS[u]["pin"]==p:
            session["user"]=u
            return redirect("/")
        flash("Invalid")
    return render("""
    <div class='card'>
    <form method=post>
    User<input name=u>
    PIN<input name=p type=password>
    <button class=btn>Login</button>
    </form></div>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ----------------------------------------------------------
# EVENTS
# ----------------------------------------------------------
@app.route("/events", methods=["GET","POST"])
def events():
    if require_login(): return require_login()
    if request.method=="POST":
        db_exec(
          "INSERT INTO events(title,date,time,status,notes) VALUES(%s,%s,%s,%s,%s)",
          (request.form["title"],request.form["date"],
           request.form["time"],request.form["status"],
           request.form["notes"])
        )
    rows=db_query("SELECT * FROM events ORDER BY date")
    body="<div class=card><h3>Events</h3><table>"
    for r in rows:
        body+=f"<tr><td>{r['date']} {r['title']}</td></tr>"
    body+="</table></div>"
    body+="""
    <div class=card>
    <form method=post>
    Title<input name=title>
    Date<input type=date name=date>
    Time<input type=time name=time>
    Status<input name=status>
    Notes<textarea name=notes></textarea>
    <button class=btn>Add</button>
    </form></div>
    """
    return render(body)
# ----------------------------------------------------------
# ROLE HELPERS
# ----------------------------------------------------------
def role():
    u = current_user()
    return u["role"] if u else None

def is_admin():
    return role() in ("SUPER_ADMIN","BRIDE_ADMIN","GROOM_ADMIN")

def is_super():
    return role()=="SUPER_ADMIN"

# ----------------------------------------------------------
# PURCHASES (Admins only)
# ----------------------------------------------------------
@app.route("/purchases", methods=["GET","POST"])
def purchases():
    if require_login(): return require_login()
    if role()=="MEMBER":
        return render("<div class='card'>Access restricted</div>")

    if request.method=="POST":
        db_exec(
          "INSERT INTO purchases(item,amount,paid_by,notes) VALUES(%s,%s,%s,%s)",
          (request.form["item"],
           float(request.form["amount"] or 0),
           request.form["paid_by"],
           request.form["notes"])
        )

    rows=db_query("SELECT * FROM purchases ORDER BY id DESC")
    body="<div class=card><h3>Purchases</h3><table>"
    for r in rows:
        body+=f"<tr><td>{r['item']}</td><td>{r['amount']}</td><td>{r['paid_by']}</td></tr>"
    body+="</table></div>"

    body+="""
    <div class=card>
    <form method=post>
    Item<input name=item required>
    Amount<input name=amount type=number step=0.01>
    Paid By<input name=paid_by>
    Notes<textarea name=notes></textarea>
    <button class=btn>Add Purchase</button>
    </form></div>
    """
    return render(body)

# ----------------------------------------------------------
# TRAVEL (Admins view/edit)
# ----------------------------------------------------------
@app.route("/travel", methods=["GET","POST"])
def travel():
    if require_login(): return require_login()
    if role()=="MEMBER":
        return render("<div class='card'>View only</div>")

    db_exec("""
    CREATE TABLE IF NOT EXISTS travel(
      id SERIAL PRIMARY KEY,
      guest TEXT,from_loc TEXT,to_loc TEXT,
      mode TEXT,notes TEXT)
    """)

    if request.method=="POST":
        db_exec(
          "INSERT INTO travel(guest,from_loc,to_loc,mode,notes) VALUES(%s,%s,%s,%s,%s)",
          (request.form["guest"],request.form["from"],
           request.form["to"],request.form["mode"],
           request.form["notes"])
        )

    rows=db_query("SELECT * FROM travel")
    body="<div class=card><h3>Travel</h3><table>"
    for r in rows:
        body+=f"<tr><td>{r['guest']}</td><td>{r['from_loc']} → {r['to_loc']}</td><td>{r['mode']}</td></tr>"
    body+="</table></div>"

    body+="""
    <div class=card>
    <form method=post>
    Guest<input name=guest>
    From<input name=from>
    To<input name=to>
    Mode<input name=mode>
    Notes<textarea name=notes></textarea>
    <button class=btn>Add Travel</button>
    </form></div>
    """
    return render(body)

# ----------------------------------------------------------
# NOTES (All users)
# ----------------------------------------------------------
@app.route("/notes", methods=["GET","POST"])
def notes():
    if require_login(): return require_login()

    db_exec("""
    CREATE TABLE IF NOT EXISTS notes(
      id SERIAL PRIMARY KEY,
      title TEXT,content TEXT,created_by TEXT)
    """)

    if request.method=="POST":
        db_exec(
          "INSERT INTO notes(title,content,created_by) VALUES(%s,%s,%s)",
          (request.form["title"],
           request.form["content"],
           current_user()["name"])
        )

    rows=db_query("SELECT * FROM notes ORDER BY id DESC")
    body="<div class=card><h3>Notes</h3>"
    for r in rows:
        body+=f"<p><b>{r['title']}</b><br>{r['content']}</p><hr>"
    body+="</div>"

    body+="""
    <div class=card>
    <form method=post>
    Title<input name=title>
    Note<textarea name=content></textarea>
    <button class=btn>Add Note</button>
    </form></div>
    """
    return render(body)

# ----------------------------------------------------------
# UPLOAD (Google Drive links)
# ----------------------------------------------------------
@app.route("/uploads", methods=["GET","POST"])
def uploads():
    if require_login(): return require_login()

    db_exec("""
    CREATE TABLE IF NOT EXISTS uploads(
      id SERIAL PRIMARY KEY,
      title TEXT,drive_link TEXT,notes TEXT)
    """)

    if request.method=="POST":
        db_exec(
          "INSERT INTO uploads(title,drive_link,notes) VALUES(%s,%s,%s)",
          (request.form["title"],
           request.form["link"],
           request.form["notes"])
        )

    rows=db_query("SELECT * FROM uploads")
    body="<div class=card><h3>Uploads (Google Drive)</h3><table>"
    for r in rows:
        body+=f"<tr><td>{r['title']}</td><td><a href='{r['drive_link']}' target=_blank>Open</a></td></tr>"
    body+="</table></div>"

    body+="""
    <div class=card>
    <form method=post>
    Title<input name=title>
    Google Drive Link<input name=link>
    Notes<textarea name=notes></textarea>
    <button class=btn>Add Link</button>
    </form></div>
    """
    return render(body)
