import sys
import os
from pathlib import Path

# Make task_manager importable
sys.path.insert(0, str(Path(__file__).parent.parent / "task_manager"))

# Tell task_app.py to use /tmp for the database
os.environ["VERCEL"] = "1"

from task_app import app, init_db

# Seed users on every cold start (Vercel is stateless)
with app.app_context():
    init_db()
