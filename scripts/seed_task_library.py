"""Run once to populate the task_library table in Supabase."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase import get_db

def main():
    db = get_db()
    data_path = Path(__file__).parent.parent / "data" / "task_library.json"
    tasks = json.loads(data_path.read_text(encoding="utf-8"))
    result = db.table("task_library").insert(tasks).execute()
    print(f"Inserted {len(result.data)} tasks into task_library.")

if __name__ == "__main__":
    main()
