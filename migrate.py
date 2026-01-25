import json
from datetime import datetime
from sqlmodel import Session, create_engine
from main import SubTask, Todo, LogEntry # Ensure main.py is in the same folder

def migrate():
    # 1. Load the data
    with open("db.json", "r") as f:
        data = json.load(f)

    engine = create_engine("sqlite:///database.db")

    with Session(engine) as session:
        # --- MIGRATE TODOS ---
        for t in data.get("todos", []):
            subtasks = [SubTask(task=s["task"], completed=s["completed"]) for s in t.get("subTasks", [])]
            new_todo = Todo(
                task=t["task"],
                completed=t["completed"],
                priority=t["priority"],
                dueDate=t.get("dueDate"),
                remindMe=t.get("remindMe", False),
                subTasks=subtasks
            )
            session.add(new_todo)

        # --- MIGRATE LOGS ---
        for l in data.get("logs", []):
            # 1. Fix Timestamp
            raw_ts = l.get("timestamp")
            if isinstance(raw_ts, str):
                l["timestamp"] = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
            else:
                l["timestamp"] = datetime.now()

            # 2. Fix URL (Ensure it's not None)
            if not l.get("url"):
                l["url"] = "Migrated / Unknown"

            # 3. Fix ID: If 'id' is in the dict but it's None or empty, remove it
            # so the model's 'default_factory' can take over.
            if "id" in l and not l["id"]:
                del l["id"]

            try:
                new_log = LogEntry(**l)
                session.add(new_log)
            except Exception as e:
                print(f"Skipping a bad log entry: {e}")

        session.commit()
        print("Migration successful!")

# if __name__ == "__main__":
#     migrate()