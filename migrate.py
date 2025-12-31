import json
import os
from sqlmodel import Session, create_engine, SQLModel
from models import Todo, SubTask, ErrorLog

# 1. Database Connection String
# If running locally, paste your Vercel/Neon string here
# IMPORTANT: SQLAlchemy requires 'postgresql://' not 'postgres://'
DATABASE_URL = os.getenv("POSTGRES_URL", "PASTE_YOUR_CONNECTION_STRING_HERE")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def run_migration():
    # 2. Create the tables in the database
    print("Creating tables...")
    SQLModel.metadata.create_all(engine)

    # 3. Load your existing JSON data
    if not os.path.exists("db.json"):
        print("Error: db.json not found.")
        return

    with open("db.json", "r") as f:
        data = json.load(f)

    with Session(engine) as session:
        print("Migrating Todos and Subtasks...")
        for t_json in data.get("todos", []):
            # Create Todo object (mapping JSON 'Notes' to Model 'notes')
            new_todo = Todo(
                task=t_json.get("task"),
                completed=t_json.get("completed", False),
                priority=t_json.get("priority", "Medium"),
                dueDate=t_json.get("dueDate"),
                startDate=t_json.get("startDate"),
                reminderDate=t_json.get("reminderDate"),
                remindMe=t_json.get("remindMe", False),
                notes=t_json.get("Notes", []) # Map capital N to lowercase n
            )

            # Add SubTasks if they exist
            for st_json in t_json.get("subTasks", []):
                new_sub = SubTask(
                    task=st_json.get("task"),
                    completed=st_json.get("completed", False)
                )
                new_todo.subTasks.append(new_sub)

            session.add(new_todo)

        print("Migrating Logs...")
        for l_json in data.get("logs", []):
            # Map JSON 'location' to Model 'url'
            new_log = ErrorLog(
                message=l_json.get("message"),
                stack=l_json.get("stack"),
                url=l_json.get("location", l_json.get("url", "unknown")),
                timestamp=l_json.get("timestamp")
            )
            session.add(new_log)

        # 4. Commit all changes
        session.commit()
        print("--- Migration Successful! ---")
        print(f"Migrated {len(data.get('todos', []))} todos.")
        print(f"Migrated {len(data.get('logs', []))} logs.")

if __name__ == "__main__":
    run_migration()