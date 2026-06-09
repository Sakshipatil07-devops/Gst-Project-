from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, date, timedelta
from io import StringIO
from pathlib import Path
from functools import wraps

from flask import (Flask, flash, g, make_response, redirect, render_template,
                   request, url_for, session, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash

import os

BASE_DIR = Path(__file__).resolve().parent
# Vercel filesystem is read-only except /tmp
DATABASE = Path("/tmp/aarms_tasks.db") if os.environ.get("VERCEL") else BASE_DIR / "aarms_tasks.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "aarms-group-taskmanager-2024-secret-key"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_PERMANENT"] = True

PRIORITIES  = ["low", "medium", "high", "urgent"]
STATUSES    = ["pending", "in_progress", "completed", "on_hold"]
DEPARTMENTS = [
    "Management", "IT & Technology", "Sales & Business Development",
    "Human Resources", "Finance & Accounts", "Operations & Logistics",
    "Marketing & Communications", "Legal & Compliance",
]
CATEGORIES = [
    "Project", "Meeting", "Report", "Review",
    "Training", "Client Work", "Admin", "Research", "Development", "Other",
]
INITIAL_USERS = [
    ("admin",  "Admin@2024",  "Admin User",     "admin@aarmsgroup.com",   "Management",                  "Administrator"),
    ("sakshi", "Sakshi@2024", "Sakshi Sharma",  "sakshi@aarmsgroup.com",  "Human Resources",             "HR Manager"),
    ("rahul",  "Rahul@2024",  "Rahul Mehta",    "rahul@aarmsgroup.com",   "Sales & Business Development","Sales Executive"),
    ("priya",  "Priya@2024",  "Priya Patel",    "priya@aarmsgroup.com",   "Finance & Accounts",          "Finance Analyst"),
    ("vikram", "Vikram@2024", "Vikram Singh",   "vikram@aarmsgroup.com",  "IT & Technology",             "IT Developer"),
    ("anita",  "Anita@2024",  "Anita Kumar",    "anita@aarmsgroup.com",   "Operations & Logistics",      "Operations Manager"),
]

TASK_JOIN = """
    SELECT t.*,
           u1.full_name  AS assignee_name,
           u1.department AS assignee_dept,
           u1.role       AS assignee_role,
           u2.full_name  AS assigner_name,
           u3.full_name  AS archiver_name
    FROM tasks t
    LEFT JOIN users u1 ON t.assigned_to  = u1.id
    LEFT JOIN users u2 ON t.assigned_by  = u2.id
    LEFT JOIN users u3 ON t.archived_by  = u3.id
"""

# ── DB ─────────────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db: db.close()

@app.context_processor
def inject_globals():
    overdue_count = 0
    if "user_id" in session:
        today = date.today().isoformat()
        overdue_count = get_db().execute(
            "SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND is_archived=0"
            " AND status NOT IN ('completed','on_hold')"
            " AND due_date IS NOT NULL AND due_date!='' AND due_date<?",
            (session["user_id"], today),
        ).fetchone()[0]
    return dict(overdue_count=overdue_count)

def init_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row

    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name     TEXT NOT NULL,
        email         TEXT NOT NULL UNIQUE,
        department    TEXT NOT NULL,
        role          TEXT NOT NULL,
        is_active     INTEGER NOT NULL DEFAULT 1,
        created_at    TEXT NOT NULL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        description TEXT DEFAULT '',
        assigned_to INTEGER REFERENCES users(id),
        assigned_by INTEGER REFERENCES users(id),
        due_date    TEXT,
        priority    TEXT NOT NULL DEFAULT 'medium',
        status      TEXT NOT NULL DEFAULT 'pending',
        department  TEXT DEFAULT '',
        category    TEXT DEFAULT 'Other',
        notes       TEXT DEFAULT '',
        is_archived INTEGER NOT NULL DEFAULT 0,
        archived_at TEXT,
        archived_by INTEGER REFERENCES users(id),
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS task_comments (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id    INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        comment    TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS task_activity (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id    INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
        user_id    INTEGER NOT NULL REFERENCES users(id),
        action     TEXT NOT NULL,
        details    TEXT DEFAULT '',
        created_at TEXT NOT NULL
    )""")

    db.commit()

    # Safe migrations for existing databases
    for sql in [
        "ALTER TABLE tasks ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE tasks ADD COLUMN archived_at TEXT",
        "ALTER TABLE tasks ADD COLUMN archived_by INTEGER",
    ]:
        try:
            db.execute(sql); db.commit()
        except Exception:
            pass

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for username, password, full_name, email, department, role in INITIAL_USERS:
        if not db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
            db.execute(
                "INSERT INTO users (username,password_hash,full_name,email,department,role,created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (username, generate_password_hash(password), full_name, email, department, role, now),
            )
    db.commit()
    db.close()

# ── Helpers ────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def current_user():
    if "user_id" not in session: return None
    return get_db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

def is_admin():
    return session.get("role") == "Administrator"

def log_activity(db, task_id: int, user_id: int, action: str, details: str = ""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO task_activity (task_id,user_id,action,details,created_at) VALUES (?,?,?,?,?)",
        (task_id, user_id, action, details, now),
    )

def user_stats(user_id: int, all_tasks: bool = False) -> dict:
    db    = get_db()
    today = date.today().isoformat()
    cond  = "is_archived=0" if all_tasks else "assigned_to=? AND is_archived=0"
    p     = [] if all_tasks else [user_id]
    total       = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {cond}", p).fetchone()[0]
    completed   = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {cond} AND status='completed'", p).fetchone()[0]
    pending     = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {cond} AND status='pending'", p).fetchone()[0]
    in_progress = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {cond} AND status='in_progress'", p).fetchone()[0]
    on_hold     = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {cond} AND status='on_hold'", p).fetchone()[0]
    overdue = db.execute(
        f"SELECT COUNT(*) FROM tasks WHERE {cond}"
        " AND status NOT IN ('completed','on_hold')"
        " AND due_date IS NOT NULL AND due_date!='' AND due_date<?",
        p + [today],
    ).fetchone()[0]
    due_today = db.execute(
        f"SELECT COUNT(*) FROM tasks WHERE {cond}"
        " AND status NOT IN ('completed','on_hold') AND due_date=?",
        p + [today],
    ).fetchone()[0]
    return dict(
        total=total, completed=completed, pending=pending,
        in_progress=in_progress, on_hold=on_hold,
        overdue=overdue, due_today=due_today,
        completion_pct=round(completed / total * 100 if total else 0, 1),
    )

def overdue_count_for_user(user_id: int) -> int:
    today = date.today().isoformat()
    return get_db().execute(
        "SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND is_archived=0"
        " AND status NOT IN ('completed','on_hold')"
        " AND due_date IS NOT NULL AND due_date!='' AND due_date<?",
        (user_id, today),
    ).fetchone()[0]

# ── Auth ───────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        db   = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.permanent    = True
            session["user_id"]    = user["id"]
            session["username"]   = user["username"]
            session["full_name"]  = user["full_name"]
            session["department"] = user["department"]
            session["role"]       = user["role"]
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))

# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    user      = current_user()
    db        = get_db()
    today     = date.today().isoformat()
    three_days = (date.today() + timedelta(days=3)).isoformat()
    admin     = is_admin()
    stats     = user_stats(user["id"], admin)

    cond   = "t.is_archived=0" if admin else "t.assigned_to=? AND t.is_archived=0"
    base_p = [] if admin else [user["id"]]

    recent   = db.execute(TASK_JOIN + f" WHERE {cond} ORDER BY t.created_at DESC LIMIT 8", base_p).fetchall()
    overdue  = db.execute(
        TASK_JOIN + f" WHERE {cond} AND t.status NOT IN ('completed','on_hold')"
        " AND t.due_date IS NOT NULL AND t.due_date!='' AND t.due_date<?"
        " ORDER BY t.due_date ASC LIMIT 5", base_p + [today]).fetchall()
    upcoming = db.execute(
        TASK_JOIN + f" WHERE {cond} AND t.status NOT IN ('completed','on_hold')"
        " AND t.due_date>=? ORDER BY t.due_date ASC LIMIT 6", base_p + [today]).fetchall()
    due_soon = db.execute(
        TASK_JOIN + f" WHERE {cond} AND t.status NOT IN ('completed','on_hold')"
        " AND t.due_date IS NOT NULL AND t.due_date>=? AND t.due_date<=?"
        " ORDER BY t.due_date ASC LIMIT 5", base_p + [today, three_days]).fetchall()
    dept_stats = db.execute(
        "SELECT department, COUNT(*) as count,"
        " SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as done"
        " FROM tasks WHERE is_archived=0 GROUP BY department ORDER BY count DESC").fetchall()

    overdue_badge = overdue_count_for_user(user["id"])
    hour      = datetime.now().hour
    greeting  = "Good Morning" if hour < 12 else ("Good Afternoon" if hour < 17 else "Good Evening")

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    return render_template("dashboard.html",
        user=user, stats=stats, recent=recent, overdue=overdue,
        upcoming=upcoming, due_soon=due_soon, dept_stats=dept_stats,
        today=today, tomorrow=tomorrow, three_days=three_days,
        admin=admin, greeting=greeting, overdue_badge=overdue_badge)

# ── Tasks list ─────────────────────────────────────────────────────────────────

@app.route("/tasks")
@login_required
def tasks_list():
    user  = current_user()
    db    = get_db()
    today = date.today().isoformat()
    admin = is_admin()

    search   = request.args.get("search", "").strip()
    status_f = request.args.get("status", "")
    prio_f   = request.args.get("priority", "")
    dept_f   = request.args.get("department", "")
    cat_f    = request.args.get("category", "")
    sort_by  = request.args.get("sort", "due_asc")
    view     = request.args.get("view", "my")

    q = TASK_JOIN + " WHERE t.is_archived=0"
    p: list = []
    if not admin or view == "my":
        q += " AND t.assigned_to=?"; p.append(user["id"])
    if search:
        q += " AND (t.title LIKE ? OR t.description LIKE ?)"; p += [f"%{search}%"]*2
    if status_f in STATUSES:
        q += " AND t.status=?"; p.append(status_f)
    if prio_f in PRIORITIES:
        q += " AND t.priority=?"; p.append(prio_f)
    if dept_f:
        q += " AND t.department=?"; p.append(dept_f)
    if cat_f:
        q += " AND t.category=?"; p.append(cat_f)

    sort_map = {
        "due_asc":   "CASE WHEN t.due_date IS NULL OR t.due_date='' THEN 1 ELSE 0 END, t.due_date ASC",
        "due_desc":  "CASE WHEN t.due_date IS NULL OR t.due_date='' THEN 1 ELSE 0 END, t.due_date DESC",
        "prio_desc": "CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END",
        "created":   "t.created_at DESC",
        "title":     "t.title COLLATE NOCASE ASC",
    }
    q += f" ORDER BY {sort_map.get(sort_by, 't.due_date ASC')}"

    all_tasks    = db.execute(q, p).fetchall()
    stats        = user_stats(user["id"], admin)
    arch_count   = db.execute("SELECT COUNT(*) FROM tasks WHERE is_archived=1").fetchone()[0]
    overdue_badge = overdue_count_for_user(user["id"])

    return render_template("tasks.html",
        tasks=all_tasks, stats=stats, today=today,
        search=search, status_f=status_f, prio_f=prio_f,
        dept_f=dept_f, cat_f=cat_f, sort_by=sort_by,
        view=view, admin=admin, user=user,
        departments=DEPARTMENTS, priorities=PRIORITIES,
        statuses=STATUSES, categories=CATEGORIES,
        arch_count=arch_count, overdue_badge=overdue_badge)

# ── Add task ───────────────────────────────────────────────────────────────────

@app.route("/tasks/add", methods=["GET", "POST"])
@login_required
def add_task():
    if not is_admin():
        flash("Only administrators can create tasks.", "danger")
        return redirect(url_for("dashboard"))
    user      = current_user()
    db        = get_db()
    all_users = db.execute("SELECT id,full_name,department FROM users WHERE is_active=1 ORDER BY full_name").fetchall()

    if request.method == "POST":
        title       = request.form.get("title","").strip()
        description = request.form.get("description","").strip()
        assigned_to = request.form.get("assigned_to","").strip()
        due_date    = request.form.get("due_date","").strip()
        priority    = request.form.get("priority","medium")
        department  = request.form.get("department","")
        category    = request.form.get("category","Other")
        notes       = request.form.get("notes","").strip()

        errors = []
        if not title: errors.append("Task title is required.")
        if priority not in PRIORITIES: errors.append("Invalid priority.")
        assigned_to_id = None
        if assigned_to:
            try: assigned_to_id = int(assigned_to)
            except ValueError: errors.append("Invalid assignee.")

        if errors:
            for e in errors: flash(e, "danger")
            return render_template("task_form.html", user=user, all_users=all_users,
                departments=DEPARTMENTS, priorities=PRIORITIES, categories=CATEGORIES, edit_mode=False)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = db.execute("""
            INSERT INTO tasks (title,description,assigned_to,assigned_by,due_date,
                priority,department,category,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (title,description,assigned_to_id,user["id"],due_date or None,
             priority,department,category,notes,now,now))
        log_activity(db, cur.lastrowid, user["id"], "created",
                     f"Task created by {user['full_name']}")
        db.commit()
        flash(f'Task "{title}" created successfully!', "success")
        return redirect(url_for("tasks_list"))

    return render_template("task_form.html", user=user, all_users=all_users,
        departments=DEPARTMENTS, priorities=PRIORITIES, categories=CATEGORIES, edit_mode=False)

# ── Task detail ────────────────────────────────────────────────────────────────

@app.route("/tasks/<int:tid>")
@login_required
def task_detail(tid):
    user = current_user()
    db   = get_db()
    task = db.execute(TASK_JOIN + " WHERE t.id=?", (tid,)).fetchone()
    if not task:
        flash("Task not found.", "danger"); return redirect(url_for("tasks_list"))

    admin    = is_admin()
    can_edit = admin or task["assigned_to"] == user["id"] or task["assigned_by"] == user["id"]
    today    = date.today().isoformat()

    comments = db.execute("""
        SELECT tc.*, u.full_name AS user_name, u.department AS user_dept
        FROM task_comments tc JOIN users u ON tc.user_id=u.id
        WHERE tc.task_id=? ORDER BY tc.created_at ASC""", (tid,)).fetchall()

    activity = db.execute("""
        SELECT ta.*, u.full_name AS user_name
        FROM task_activity ta JOIN users u ON ta.user_id=u.id
        WHERE ta.task_id=? ORDER BY ta.created_at DESC LIMIT 25""", (tid,)).fetchall()

    return render_template("task_detail.html",
        task=task, user=user, today=today,
        can_edit=can_edit, admin=admin, statuses=STATUSES,
        comments=comments, activity=activity)

# ── Edit task ──────────────────────────────────────────────────────────────────

@app.route("/tasks/edit/<int:tid>", methods=["GET", "POST"])
@login_required
def edit_task(tid):
    user = current_user()
    db   = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=? AND is_archived=0", (tid,)).fetchone()
    if not task:
        flash("Task not found.", "danger"); return redirect(url_for("tasks_list"))

    if not is_admin():
        flash("Only administrators can edit tasks.", "danger")
        return redirect(url_for("task_detail", tid=tid))

    all_users = db.execute("SELECT id,full_name,department FROM users WHERE is_active=1 ORDER BY full_name").fetchall()

    if request.method == "POST":
        title       = request.form.get("title","").strip()
        description = request.form.get("description","").strip()
        assigned_to = request.form.get("assigned_to","").strip()
        due_date    = request.form.get("due_date","").strip()
        priority    = request.form.get("priority","medium")
        status      = request.form.get("status","pending")
        department  = request.form.get("department","")
        category    = request.form.get("category","Other")
        notes       = request.form.get("notes","").strip()

        errors = []
        if not title: errors.append("Title is required.")
        if priority not in PRIORITIES: errors.append("Invalid priority.")
        if status not in STATUSES: errors.append("Invalid status.")
        assigned_to_id = None
        if assigned_to:
            try: assigned_to_id = int(assigned_to)
            except ValueError: errors.append("Invalid assignee.")

        if errors:
            for e in errors: flash(e, "danger")
            return render_template("task_form.html", task=task, user=user, all_users=all_users,
                departments=DEPARTMENTS, priorities=PRIORITIES,
                statuses=STATUSES, categories=CATEGORIES, edit_mode=True)

        changes = []
        if task["status"]   != status:   changes.append(f"Status: {task['status'].replace('_',' ').title()} → {status.replace('_',' ').title()}")
        if task["priority"] != priority: changes.append(f"Priority: {task['priority'].title()} → {priority.title()}")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("""UPDATE tasks SET title=?,description=?,assigned_to=?,due_date=?,
            priority=?,status=?,department=?,category=?,notes=?,updated_at=? WHERE id=?""",
            (title,description,assigned_to_id,due_date or None,
             priority,status,department,category,notes,now,tid))
        detail = "; ".join(changes) + f" — edited by {user['full_name']}" if changes else f"Task edited by {user['full_name']}"
        log_activity(db, tid, user["id"], "edited", detail)
        db.commit()
        flash(f'Task "{title}" updated!', "success")
        return redirect(url_for("task_detail", tid=tid))

    return render_template("task_form.html", task=task, user=user, all_users=all_users,
        departments=DEPARTMENTS, priorities=PRIORITIES,
        statuses=STATUSES, categories=CATEGORIES, edit_mode=True)

# ── Delete to bin (soft delete, 30-day recovery) ──────────────────────────────

@app.route("/tasks/delete/<int:tid>", methods=["POST"])
@login_required
def delete_task(tid):
    if not is_admin():
        flash("Only administrators can delete tasks.", "danger")
        return redirect(url_for("tasks_list"))
    user = current_user()
    db   = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=? AND is_archived=0", (tid,)).fetchone()
    if not task:
        flash("Task not found.", "danger"); return redirect(url_for("tasks_list"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("UPDATE tasks SET is_archived=1,archived_at=?,archived_by=?,updated_at=? WHERE id=?",
               (now, user["id"], now, tid))
    log_activity(db, tid, user["id"], "archived", f"Moved to bin by {user['full_name']}")
    db.commit()
    flash(f'"{task["title"]}" moved to Recovery Bin (auto-deleted after 30 days).', "warning")
    return redirect(request.form.get("next", url_for("tasks_list")))

# ── Restore from bin ───────────────────────────────────────────────────────────

@app.route("/tasks/restore/<int:tid>", methods=["POST"])
@login_required
def restore_task(tid):
    if not is_admin():
        flash("Only administrators can restore tasks.", "danger")
        return redirect(url_for("dashboard"))
    user = current_user()
    db   = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=? AND is_archived=1", (tid,)).fetchone()
    if not task:
        flash("Task not found in bin.", "danger"); return redirect(url_for("recovery_bin"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("UPDATE tasks SET is_archived=0,archived_at=NULL,archived_by=NULL,updated_at=? WHERE id=?",
               (now, tid))
    log_activity(db, tid, user["id"], "restored", f"Restored by {user['full_name']}")
    db.commit()
    flash(f'"{task["title"]}" restored to active tasks.', "success")
    return redirect(url_for("recovery_bin"))

# ── Purge from bin (permanent delete) ─────────────────────────────────────────

@app.route("/tasks/purge/<int:tid>", methods=["POST"])
@login_required
def purge_task(tid):
    if not is_admin():
        flash("Only administrators can permanently delete tasks.", "danger")
        return redirect(url_for("dashboard"))
    db   = get_db()
    task = db.execute("SELECT title FROM tasks WHERE id=?", (tid,)).fetchone()
    if not task:
        flash("Task not found.", "danger"); return redirect(url_for("recovery_bin"))
    db.execute("DELETE FROM tasks WHERE id=?", (tid,))
    db.commit()
    flash(f'"{task["title"]}" permanently deleted.', "danger")
    return redirect(url_for("recovery_bin"))

# ── Recovery Bin ───────────────────────────────────────────────────────────────

@app.route("/tasks/bin")
@login_required
def recovery_bin():
    if not is_admin():
        flash("Only administrators can access the Recovery Bin.", "danger")
        return redirect(url_for("dashboard"))
    db    = get_db()
    today = date.today()
    # Auto-purge items older than 30 days
    cutoff = (today - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute("DELETE FROM tasks WHERE is_archived=1 AND archived_at IS NOT NULL AND archived_at<?", (cutoff,))
    db.commit()
    # Load remaining bin items with days remaining
    rows  = db.execute(TASK_JOIN + " WHERE t.is_archived=1 ORDER BY t.archived_at DESC").fetchall()
    tasks = []
    for r in rows:
        days_left = 30
        if r["archived_at"]:
            deleted_date = date.fromisoformat(r["archived_at"][:10])
            days_left    = 30 - (today - deleted_date).days
        tasks.append({"task": r, "days_left": max(days_left, 0)})
    return render_template("recovery_bin.html", tasks=tasks, user=current_user())

# ── Toggle / set status ────────────────────────────────────────────────────────

@app.route("/tasks/toggle/<int:tid>", methods=["POST"])
@login_required
def toggle_task(tid):
    user = current_user()
    db   = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=? AND is_archived=0", (tid,)).fetchone()
    if not task:
        flash("Task not found.", "danger"); return redirect(url_for("tasks_list"))
    new_status = "completed" if task["status"] != "completed" else "pending"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?", (new_status, now, tid))
    log_activity(db, tid, user["id"], "status_changed",
                 f"Status: {task['status'].replace('_',' ').title()} → {new_status.replace('_',' ').title()}")
    db.commit()
    flash(f'"{task["title"]}" {"completed" if new_status=="completed" else "re-opened"}!', "success")
    return redirect(request.form.get("next", url_for("tasks_list")))

@app.route("/tasks/setstatus/<int:tid>", methods=["POST"])
@login_required
def set_status(tid):
    user       = current_user()
    new_status = request.form.get("status","")
    if new_status not in STATUSES:
        flash("Invalid status.", "danger"); return redirect(url_for("tasks_list"))
    db   = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=? AND is_archived=0", (tid,)).fetchone()
    if not task:
        flash("Task not found.", "danger"); return redirect(url_for("tasks_list"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?", (new_status, now, tid))
    log_activity(db, tid, user["id"], "status_changed",
                 f"Status: {task['status'].replace('_',' ').title()} → {new_status.replace('_',' ').title()}")
    db.commit()
    flash(f"Status updated to {new_status.replace('_',' ').title()}.", "success")
    return redirect(request.form.get("next", url_for("tasks_list")))

# ── Comment ────────────────────────────────────────────────────────────────────

@app.route("/tasks/<int:tid>/comment", methods=["POST"])
@login_required
def add_comment(tid):
    user    = current_user()
    db      = get_db()
    comment = request.form.get("comment","").strip()
    task    = db.execute("SELECT id FROM tasks WHERE id=? AND is_archived=0", (tid,)).fetchone()
    if not task:
        flash("Task not found.", "danger"); return redirect(url_for("tasks_list"))
    if not comment:
        flash("Comment cannot be empty.", "warning"); return redirect(url_for("task_detail", tid=tid))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute("INSERT INTO task_comments (task_id,user_id,comment,created_at) VALUES (?,?,?,?)",
               (tid, user["id"], comment, now))
    log_activity(db, tid, user["id"], "commented", f"Comment added by {user['full_name']}")
    db.commit()
    flash("Comment posted.", "success")
    return redirect(url_for("task_detail", tid=tid) + "#comments")

# ── Profile + change password ──────────────────────────────────────────────────

@app.route("/profile")
@login_required
def profile():
    user     = current_user()
    db       = get_db()
    today    = date.today().isoformat()
    stats    = user_stats(user["id"])
    my_tasks = db.execute(
        TASK_JOIN + " WHERE t.assigned_to=? AND t.is_archived=0 ORDER BY t.due_date ASC",
        (user["id"],)).fetchall()
    return render_template("profile.html", user=user, stats=stats, my_tasks=my_tasks, today=today)

@app.route("/profile/change-password", methods=["POST"])
@login_required
def change_password():
    user       = current_user()
    db         = get_db()
    current_pw = request.form.get("current_password","")
    new_pw     = request.form.get("new_password","")
    confirm_pw = request.form.get("confirm_password","")

    if not check_password_hash(user["password_hash"], current_pw):
        flash("Current password is incorrect.", "danger")
    elif len(new_pw) < 6:
        flash("New password must be at least 6 characters.", "danger")
    elif new_pw != confirm_pw:
        flash("New passwords do not match.", "danger")
    else:
        db.execute("UPDATE users SET password_hash=? WHERE id=?",
                   (generate_password_hash(new_pw), user["id"]))
        db.commit()
        flash("Password changed successfully.", "success")
    return redirect(url_for("profile") + "#change-password")

# ── Admin: users ───────────────────────────────────────────────────────────────

@app.route("/admin/users")
@login_required
def admin_users():
    if not is_admin():
        flash("Administrators only.", "danger"); return redirect(url_for("dashboard"))
    db    = get_db()
    raw   = db.execute("SELECT * FROM users WHERE is_active=1 ORDER BY department,full_name").fetchall()
    users = []
    for u in raw:
        s = user_stats(u["id"])
        users.append({
            "id": u["id"], "full_name": u["full_name"], "role": u["role"],
            "department": u["department"], "email": u["email"],
            "total": s["total"], "completed": s["completed"], "pending": s["pending"],
            "in_progress": s["in_progress"], "on_hold": s["on_hold"],
            "overdue": s["overdue"], "completion_pct": s["completion_pct"],
        })
    return render_template("admin_users.html", user=current_user(), users=users)

# ── Export CSV ─────────────────────────────────────────────────────────────────

@app.route("/tasks/export")
@login_required
def export_tasks():
    user  = current_user()
    db    = get_db()
    admin = is_admin()
    view  = request.args.get("view","my")

    q = """SELECT t.id,t.title,t.description,t.status,t.priority,t.department,
                  t.category,t.due_date,t.notes,t.created_at,t.updated_at,
                  u1.full_name AS assignee, u2.full_name AS assigner
           FROM tasks t
           LEFT JOIN users u1 ON t.assigned_to=u1.id
           LEFT JOIN users u2 ON t.assigned_by=u2.id
           WHERE t.is_archived=0"""
    p: list = []
    if not admin or view == "my":
        q += " AND t.assigned_to=?"; p.append(user["id"])
    q += " ORDER BY t.due_date ASC"

    rows = db.execute(q, p).fetchall()
    si   = StringIO()
    w    = csv.writer(si)
    w.writerow(["ID","Title","Description","Status","Priority","Department",
                "Category","Due Date","Assigned To","Assigned By","Notes","Created","Updated"])
    for r in rows:
        w.writerow([r["id"],r["title"],r["description"],r["status"],r["priority"],
                    r["department"],r["category"],r["due_date"] or "",
                    r["assignee"] or "",r["assigner"] or "",
                    r["notes"],r["created_at"],r["updated_at"]])
    resp = make_response(si.getvalue().encode("utf-8-sig"))
    resp.headers["Content-Disposition"] = f'attachment; filename=aarms_tasks_{date.today()}.csv'
    resp.headers["Content-Type"] = "text/csv; charset=utf-8-sig"
    return resp

# ── Seed ───────────────────────────────────────────────────────────────────────

@app.route("/seed")
@login_required
def seed_data():
    if not is_admin():
        flash("Administrators only.", "danger"); return redirect(url_for("dashboard"))
    db    = get_db()
    if db.execute("SELECT COUNT(*) FROM tasks WHERE is_archived=0").fetchone()[0] > 0:
        flash("Demo data already loaded.", "warning"); return redirect(url_for("dashboard"))

    today = date.today()
    now   = datetime.now()
    uids  = {r["username"]: r["id"] for r in db.execute("SELECT id,username FROM users").fetchall()}

    demo = [
        ("Q2 Sales Report Preparation","Compile quarterly sales figures and present to management board.","rahul","admin",3,"high","in_progress","Sales & Business Development","Report","Include region-wise breakdown"),
        ("New Employee Onboarding — June","Prepare onboarding kits for 3 new hires joining next week.","sakshi","admin",5,"high","pending","Human Resources","Admin","Coordinate with IT for laptop and access setup"),
        ("Monthly Payroll Processing","Process payroll for all 45 employees. Verify HRA components.","priya","admin",2,"urgent","pending","Finance & Accounts","Admin","Cross-check attendance before processing"),
        ("AWS Server Migration","Migrate production infrastructure to AWS with zero downtime.","vikram","admin",14,"high","in_progress","IT & Technology","Project","Stage migration in 3 phases; test rollback"),
        ("Warehouse Inventory Audit Q2","Conduct bi-annual inventory check across all 3 warehouses.","anita","admin",7,"medium","pending","Operations & Logistics","Review","Coordinate with warehouse managers"),
        ("Client Proposal — ABC Corp","Prepare proposal for ABC Corp supply contract renewal.","rahul","admin",-1,"urgent","completed","Sales & Business Development","Client Work","Include 2 case studies and competitive pricing"),
        ("Performance Review Cycle Q2","Initiate Q2 performance reviews for all departments.","sakshi","admin",10,"high","pending","Human Resources","Review","Send review forms to all department heads"),
        ("GST Filing — May 2024","Prepare and submit GST returns for May 2024.","priya","admin",-3,"urgent","completed","Finance & Accounts","Admin","Verified with accounts receivable; filed on time"),
        ("Website Security Audit","Conduct comprehensive security review of company website.","vikram","admin",6,"high","pending","IT & Technology","Review","Check OWASP Top 10; generate detailed report"),
        ("Logistics Route Optimisation","Analyse delivery routes and propose cost-reduction plan.","anita","admin",21,"medium","pending","Operations & Logistics","Project","Target 15% cost reduction"),
        ("Brand Guidelines Update","Revise and publish updated company brand style guide.","admin","admin",15,"low","pending","Management","Project","Include updated colour palette and typography"),
        ("Data Security Training","Organise mandatory training for all staff on data security.","sakshi","admin",8,"medium","pending","Human Resources","Training","Book training hall; send calendar invites"),
        ("FY2025 Budget Planning","Prepare department-wise budget proposals for FY2025.","priya","admin",30,"high","pending","Finance & Accounts","Project","Align with 3-year strategic objectives"),
        ("CRM Upgrade v3.1","Upgrade CRM to latest version with new pipeline features.","vikram","admin",12,"medium","in_progress","IT & Technology","Development","Test in staging before production push"),
        ("Vendor Contract Renewal","Review and renew annual contracts with top 5 vendors.","anita","admin",-2,"high","completed","Operations & Logistics","Client Work","Negotiated improved payment terms; saved 8%"),
    ]

    for i, row in enumerate(demo):
        title,desc,ato,aby,due_off,prio,status,dept,cat,notes = row
        due     = (today + timedelta(days=due_off)).isoformat()
        created = (now - timedelta(days=len(demo)-i)).strftime("%Y-%m-%d %H:%M:%S")
        cur = db.execute("""INSERT INTO tasks
            (title,description,assigned_to,assigned_by,due_date,priority,status,department,category,notes,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (title,desc,uids.get(ato),uids.get(aby),due,prio,status,dept,cat,notes,created,created))
        log_activity(db, cur.lastrowid, uids.get(aby, uids["admin"]),
                     "created", f"Task created by Admin User")

    db.commit()
    flash(f"{len(demo)} demo tasks loaded!", "success")
    return redirect(url_for("dashboard"))

# ── API ────────────────────────────────────────────────────────────────────────

@app.route("/api/tasks")
@login_required
def api_tasks():
    user  = current_user()
    db    = get_db()
    admin = is_admin()
    cond  = "t.is_archived=0" if admin else "t.assigned_to=? AND t.is_archived=0"
    p     = [] if admin else [user["id"]]
    return jsonify([dict(r) for r in db.execute(TASK_JOIN + f" WHERE {cond} ORDER BY t.due_date ASC", p).fetchall()])

@app.route("/api/stats")
@login_required
def api_stats():
    return jsonify(user_stats(current_user()["id"], is_admin()))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
else:
    init_db()
