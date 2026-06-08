# TaskMaster Pro — Task Management System

A full-featured web-based Task Management System built with **Python Flask** and **SQLite**.

---

## Features

### Core (Required)
| Feature | Description |
|---|---|
| Create Tasks | Add tasks with title, description, priority, category, due date, and notes |
| View All Tasks | Paginated table with search, filter, and sort |
| Edit Tasks | Full edit form with all fields including status toggle |
| Delete Tasks | Single delete with confirmation modal; bulk delete |
| Status Toggle | One-click toggle between Pending and Completed |
| Search | Search across title, description, and notes |
| Filter | Filter by status, priority, and category |

### Extra Features
| Feature | Description |
|---|---|
| **Dashboard** | Live stats: Total, Completed, Pending, Overdue, Due Today, Urgent |
| **Progress Bar** | Animated completion percentage bar |
| **Charts** | Doughnut chart (priority breakdown) + Bar chart (category breakdown) using Chart.js |
| **Priority Levels** | Low / Medium / High / Urgent — Urgent has a pulsing animation |
| **Due Date Tracking** | Overdue tasks highlighted in red; due-today in orange |
| **Task Categories** | Predefined + create new categories on the fly |
| **Task Detail View** | Full task page with all information and inline edit/delete |
| **Bulk Actions** | Select multiple tasks → Mark complete / Mark pending / Delete |
| **Export CSV** | Download all tasks (or filtered) as a spreadsheet |
| **Dark / Light Mode** | Persistent toggle saved in localStorage |
| **REST API** | `GET /api/tasks` and `GET /api/stats` JSON endpoints |
| **Demo Data** | One-click `/seed` route loads 12 realistic sample tasks |
| **Toast Notifications** | Auto-dismiss success/error/warning notifications |
| **Responsive Design** | Mobile-friendly Bootstrap 5 layout |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+ / Flask 3.x |
| Database | SQLite (via Python's built-in `sqlite3`) |
| Frontend | Bootstrap 5.3, Font Awesome 6.5, Chart.js 4.4 |
| Styling | Custom CSS with dark-mode support |

---

## Setup & Run

```bash
# 1. Navigate to the project folder
cd task_manager

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python task_app.py
```

Open your browser at: **http://127.0.0.1:5001**

> First run: Visit **http://127.0.0.1:5001/seed** to load 12 demo tasks.

---

## Project Structure

```
task_manager/
├── task_app.py          # Flask application (routes, DB logic)
├── tasks.db             # SQLite database (auto-created on first run)
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── templates/
│   ├── base.html        # Base layout (navbar, toasts, footer, dark mode)
│   ├── index.html       # Dashboard (stats, charts, recent tasks)
│   ├── tasks.html       # Task list (search, filter, bulk actions)
│   ├── add_task.html    # Create / Edit task form
│   └── task_detail.html # Task detail view
└── static/
    └── style.css        # Custom styles
```

---

## API Documentation

### `GET /api/tasks`
Returns all tasks as JSON.

**Query Parameters:**
| Param | Values | Description |
|---|---|---|
| `status` | `pending` / `completed` | Filter by status |
| `priority` | `low` / `medium` / `high` / `urgent` | Filter by priority |

**Example:**
```
GET /api/tasks?status=pending&priority=urgent
```

**Response:**
```json
[
  {
    "id": 1,
    "title": "Complete documentation",
    "description": "Write README...",
    "status": "pending",
    "priority": "high",
    "category": "Work",
    "due_date": "2024-12-31",
    "notes": "",
    "created_at": "2024-06-05 10:00:00",
    "updated_at": "2024-06-05 10:00:00"
  }
]
```

---

### `GET /api/stats`
Returns summary statistics as JSON.

**Response:**
```json
{
  "total": 12,
  "completed": 4,
  "pending": 8,
  "overdue": 2,
  "due_today": 1,
  "urgent": 3,
  "completion_pct": 33.3
}
```

---

## Database Schema

```sql
CREATE TABLE tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',   -- 'pending' | 'completed'
    priority    TEXT NOT NULL DEFAULT 'medium',    -- 'low' | 'medium' | 'high' | 'urgent'
    category    TEXT DEFAULT 'Other',
    due_date    TEXT,                              -- ISO date: YYYY-MM-DD
    notes       TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
```

---

## Screenshots

| Page | Description |
|---|---|
| `/` | Dashboard with stats cards, progress bar, and charts |
| `/tasks` | Full task list with search, filter, sort, and bulk actions |
| `/tasks/add` | Create task form with live priority preview |
| `/tasks/<id>` | Task detail view with all information |

---

*Built for the Task Management System project — Python Flask + SQLite + Bootstrap 5*
