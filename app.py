from flask import Flask, request, redirect, url_for, session, render_template_string
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "wedding-secret-key-change-me")

# ==========================================================
# CONFIG (edit here)
# ==========================================================
APP_TITLE = "Nidhi & Tushar Wedding"

# Roles locked as per your correction:
# Super Admin = you
# Bride Admin = Samdharsi Kumar
# Groom Admin = Tushar Garg
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

# ==========================================================
# IN-MEMORY DATA (for now)
# Later we can move to SQLite easily
# ==========================================================
EVENTS = [
    {
        "id": 1,
        "title": "Venue Finalisation",
        "date": "2026-01-25",
        "time": "11:00",
        "notes": "Finalize venue and booking confirmation.",
        "created_by": "SYSTEM",
    },
    {
        "id": 2,
        "title": "Purchasing Plan (Clothes & Jewellery)",
        "date": "2026-01-28",
        "time": "16:00",
        "notes": "List items and confirm vendors.",
        "created_by": "SYSTEM",
    },
]

GUESTS = [
    {"id": 1, "side": "BRIDE", "name": "Bride Guest 1", "relation": "Relative", "visited": False},
    {"id": 2, "side": "GROOM", "name": "Groom Guest 1", "relation": "Friend", "visited": False},
]

PURCHASES = [
    {"id": 1, "category": "Clothes", "item": "Outfit selection", "status": "Planned", "notes": ""},
    {"id": 2, "category": "Jewellery", "item": "Necklace set", "status": "Pending", "notes": ""},
]

COMMERCIALS = [
    {"id": 1, "category": "Venue", "amount": 250000, "notes": "Advance paid"},
]

# ==========================================================
# HTML TEMPLATE (Royal Theme)
# ==========================================================
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
      background: #fffaf0; /* ivory */
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
    .wrap{ padding:16px; max-width:980px; margin:auto; }
    .card{
      background:#ffffff;
      border:1px solid #e7d9b0;
      border-radius:12px;
      padding:14px;
      margin-bottom:14px;
      box-shadow:0 2px 10px rgba(0,0,0,0.04);
    }
    .row{ display:flex; gap:12px; flex-wrap:wrap; }
    .col{ flex:1; min-width:240px; }
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
    nav a{
      margin-right:10px;
      text-decoration:none;
      color:#fff;
      font-weight:600;
    }
    .danger{ color:#b00020; font-weight:700; }
    .ok{ color:#1b7f3a; font-weight:700; }
    table{
      width:100%;
      border-collapse:collapse;
      font-size:14px;
    }
    td,th{
      border-bottom:1px solid #eee;
      padding:10px 6px;
      text-align:left;
    }
    .right{ text-align:right; }
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
        <a href="{{url_for('purchases')}}">Purchases</a>
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

# ==========================================================
# Helpers
# ==========================================================
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

def render(body_html, **ctx):
    user = current_user()
    role_label = ROLE_LABELS.get(user["role"], "") if user else ""
    return render_template_string(BASE_HTML, title=APP_TITLE, body=body_html, user=user, role_label=role_label, **ctx)

# ==========================================================
# Routes
# ==========================================================
@app.route("/")
def home():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    body = f"""
    <div class="card">
      <div class="row">
        <div class="col">
          <h2 style="margin:0;">Welcome, {user["name"]} 🎉</h2>
          <div class="muted">Royal wedding planning dashboard</div>
          <div style="margin-top:10px;">
            <span class="tag">{ROLE_LABELS.get(role)}</span>
          </div>
        </div>
        <div class="col">
          <h3 style="margin:0;">Quick Actions</h3>
          <div style="margin-top:10px;">
            <a class="btn" href="{url_for('events')}">📅 View Events</a>
            <a class="btn2" href="{url_for('guests')}">👥 Guests</a>
          </div>
          <div style="margin-top:10px;">
            <a class="btn2" href="{url_for('purchases')}">🛍 Purchases</a>
            {"<a class='btn' href='"+url_for('commercials')+"'>💰 Commercials</a>" if role=="SUPER_ADMIN" else ""}
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 style="margin-top:0;">Upcoming Events</h3>
      <table>
        <tr><th>When</th><th>Title</th><th>Notes</th></tr>
    """

    for e in sorted(EVENTS, key=lambda x: (x["date"], x["time"])):
        body += f"<tr><td>{e['date']} {e['time']}</td><td><b>{e['title']}</b></td><td class='muted'>{e['notes']}</td></tr>"

    body += """
      </table>
    </div>
    """

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
                <input name="username" placeholder="vijay / samdharsi / tushar / member" required>
                <label>PIN</label>
                <input name="pin" type="password" placeholder="****" required>
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
      <p class="muted">Use one of the demo users below (change PINs later).</p>
      <form method="post">
        <label>Username</label>
        <input name="username" placeholder="vijay / samdharsi / tushar / member" required>
        <label>PIN</label>
        <input name="pin" type="password" placeholder="****" required>
        <button class="btn" type="submit">Login</button>
      </form>
      <div class="muted" style="margin-top:10px;">
        Demo users:<br>
        <b>vijay</b> (1234), <b>samdharsi</b> (1111), <b>tushar</b> (2222), <b>member</b> (0000)
      </div>
    </div>
    """
    return render(body)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

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

        if title and date_ and time_:
            new_id = max([e["id"] for e in EVENTS] + [0]) + 1
            EVENTS.append({
                "id": new_id,
                "title": title,
                "date": date_,
                "time": time_,
                "notes": notes,
                "created_by": user["name"],
            })
        return redirect(url_for("events"))

    body = """
    <div class="card">
      <h2 style="margin-top:0;">📅 Events & Activities</h2>
      <p class="muted">Pre-wedding activities + wedding rituals. Admins can add events anytime.</p>
      <table>
        <tr><th>When</th><th>Title</th><th>Notes</th><th class="right">By</th></tr>
    """
    for e in sorted(EVENTS, key=lambda x: (x["date"], x["time"])):
        body += f"""
        <tr>
          <td>{e['date']} {e['time']}</td>
          <td><b>{e['title']}</b></td>
          <td class="muted">{e['notes']}</td>
          <td class="right muted">{e.get('created_by','')}</td>
        </tr>
        """

    body += "</table></div>"

    if is_admin(role):
        body += """
        <div class="card">
          <h3 style="margin-top:0;">➕ Add Event (Admin)</h3>
          <form method="post">
            <label>Title</label>
            <input name="title" placeholder="e.g., Haldi, Venue Finalisation, Shopping" required>
            <label>Date</label>
            <input name="date" type="date" required>
            <label>Time</label>
            <input name="time" type="time" required>
            <label>Notes</label>
            <textarea name="notes" placeholder="Optional notes..."></textarea>
            <button class="btn" type="submit">Add Event</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>You have read-only access.</p></div>"

    return render(body)

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

            if name:
                new_id = max([g["id"] for g in GUESTS] + [0]) + 1
                GUESTS.append({
                    "id": new_id,
                    "side": side,
                    "name": name,
                    "relation": relation,
                    "visited": False
                })
            return redirect(url_for("guests"))

        if action == "toggle_visit":
            gid = int(request.form.get("gid"))
            for g in GUESTS:
                if g["id"] == gid:
                    g["visited"] = not g["visited"]
                    break
            return redirect(url_for("guests"))

    bride = [g for g in GUESTS if g["side"] == "BRIDE"]
    groom = [g for g in GUESTS if g["side"] == "GROOM"]

    body = """
    <div class="card">
      <h2 style="margin-top:0;">👥 Guest Management</h2>
      <p class="muted">Track guests bride-side and groom-side. Mark who has visited.</p>
    </div>

    <div class="row">
      <div class="col">
        <div class="card">
          <h3 style="margin-top:0;">Bride Side</h3>
          <table>
            <tr><th>Name</th><th>Relation</th><th>Status</th><th class="right">Action</th></tr>
    """
    for g in bride:
        status = "<span class='ok'>Visited</span>" if g["visited"] else "<span class='muted'>Not yet</span>"
        body += f"""
        <tr>
          <td><b>{g['name']}</b></td>
          <td class="muted">{g['relation']}</td>
          <td>{status}</td>
          <td class="right">
            <form method="post" style="margin:0;">
              <input type="hidden" name="action" value="toggle_visit">
              <input type="hidden" name="gid" value="{g['id']}">
              <button class="btn2" type="submit">Toggle</button>
            </form>
          </td>
        </tr>
        """

    body += """
          </table>
        </div>
      </div>

      <div class="col">
        <div class="card">
          <h3 style="margin-top:0;">Groom Side</h3>
          <table>
            <tr><th>Name</th><th>Relation</th><th>Status</th><th class="right">Action</th></tr>
    """
    for g in groom:
        status = "<span class='ok'>Visited</span>" if g["visited"] else "<span class='muted'>Not yet</span>"
        body += f"""
        <tr>
          <td><b>{g['name']}</b></td>
          <td class="muted">{g['relation']}</td>
          <td>{status}</td>
          <td class="right">
            <form method="post" style="margin:0;">
              <input type="hidden" name="action" value="toggle_visit">
              <input type="hidden" name="gid" value="{g['id']}">
              <button class="btn2" type="submit">Toggle</button>
            </form>
          </td>
        </tr>
        """

    body += """
          </table>
        </div>
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
            <label>Relation</label>
            <input name="relation" placeholder="e.g., Uncle, Friend, Cousin">
            <button class="btn" type="submit">Add Guest</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>You have read-only access.</p></div>"

    return render(body)

@app.route("/purchases", methods=["GET", "POST"])
def purchases():
    r = require_login()
    if r:
        return r

    user = current_user()
    role = user["role"]

    if request.method == "POST":
        if not is_admin(role):
            return render("<div class='card'><h2>Purchases</h2><p class='danger'>Only Admins can add purchases.</p></div>")

        category = request.form.get("category", "").strip()
        item = request.form.get("item", "").strip()
        status = request.form.get("status", "").strip()
        notes = request.form.get("notes", "").strip()

        if category and item and status:
            new_id = max([p["id"] for p in PURCHASES] + [0]) + 1
            PURCHASES.append({
                "id": new_id,
                "category": category,
                "item": item,
                "status": status,
                "notes": notes,
            })
        return redirect(url_for("purchases"))

    body = """
    <div class="card">
      <h2 style="margin-top:0;">🛍 Purchases</h2>
      <p class="muted">Track purchases like clothes, jewellery, gifts, etc.</p>
      <table>
        <tr><th>Category</th><th>Item</th><th>Status</th><th>Notes</th></tr>
    """
    for p in PURCHASES:
        body += f"""
        <tr>
          <td><b>{p['category']}</b></td>
          <td>{p['item']}</td>
          <td><span class="tag">{p['status']}</span></td>
          <td class="muted">{p['notes']}</td>
        </tr>
        """

    body += "</table></div>"

    if is_admin(role):
        body += """
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
            <input name="item" placeholder="e.g., Sherwani, Saree, Ring, Shoes" required>
            <label>Status</label>
            <select name="status">
              <option>Planned</option>
              <option>Pending</option>
              <option>Bought</option>
            </select>
            <label>Notes</label>
            <input name="notes" placeholder="Optional notes...">
            <button class="btn" type="submit">Add Purchase</button>
          </form>
        </div>
        """
    else:
        body += "<div class='card'><p class='muted'>You have read-only access.</p></div>"

    return render(body)

@app.route("/commercials")
def commercials():
    r = require_login()
    if r:
        return r

    user = current_user()
    if user["role"] != "SUPER_ADMIN":
        return render("<div class='card'><h2>Commercials</h2><p class='danger'>Access denied.</p></div>")

    total = sum(x["amount"] for x in COMMERCIALS)

    body = f"""
    <div class="card">
      <h2 style="margin-top:0;">💰 Commercials (Super Admin Only)</h2>
      <p class="muted">This section is hidden from other admins and members.</p>
      <table>
        <tr><th>Category</th><th class="right">Amount</th><th>Notes</th></tr>
    """

    for c in COMMERCIALS:
        body += f"""
        <tr>
          <td><b>{c['category']}</b></td>
          <td class="right">₹ {c['amount']}</td>
          <td class="muted">{c['notes']}</td>
        </tr>
        """

    body += f"""
      </table>
      <h3 style="margin-top:14px;">Total: ₹ {total}</h3>
    </div>
    """

    return render(body)

# ==========================================================
# Run
# ==========================================================
if __name__ == "__main__":
    # For LAN access (iPhone/Android on same WiFi)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=True)
