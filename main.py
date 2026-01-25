import os
import secrets
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import selectinload # Add this import
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import SQLModel, Field, Relationship, Session, create_engine, select
import shutil
from pathlib import Path

# --- BACKUP CONFIG ---
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True) # Creates the folder if it doesn't exist

def create_db_backup():
    if os.path.exists(sqlite_file_name):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"database_backup_{timestamp}.db"
        shutil.copy2(sqlite_file_name, backup_path)
        print(f"✅ Database backup created: {backup_path}")

load_dotenv()

# --- SQL CONFIG ---
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False} # Needed for SQLite
engine = create_engine(sqlite_url, connect_args=connect_args)

def get_session():
    with Session(engine) as session:
        yield session


class SubTaskBase(SQLModel):
    task: str
    completed: bool = False

class SubTask(SubTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    todo_id: Optional[int] = Field(default=None, foreign_key="todo.id")
    # Link back to Todo (internal use)
    todo: Optional["Todo"] = Relationship(back_populates="subTasks")

class SubTaskRead(SubTaskBase):
    id: int

class TodoBase(SQLModel):
    task: str
    completed: bool = False
    priority: str = "Medium"
    dueDate: Optional[str] = None
    remindMe: bool = False

# A plain model for incoming subtask data
class SubTaskCreate(SubTaskBase):
    pass

class TodoCreate(TodoBase):
    # This uses the plain SubTaskCreate list, not the DB Table list
    subTasks: List[SubTaskCreate] = []

# A plain model for incoming Todo data
class TodoUpdate(TodoBase):
    # Here we use the plain SubTaskCreate model, NOT the SubTask table
    subTasks: List[SubTaskCreate] = []

class Todo(TodoBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # Relationship with eager loading enabled
    subTasks: List[SubTask] = Relationship(
        back_populates="todo",
        cascade_delete=True,
        sa_relationship_kwargs={"lazy": "selectin"}
    )

class TodoRead(TodoBase):
    id: int
    # This is the "Magic" line that forces the subTasks into the JSON
    subTasks: List[SubTaskRead] = []

class LogEntry(SQLModel, table=True):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4())[:8],
        primary_key=True
    )
    message: str
    stack: str = "No stack trace available"
    url: Optional[str] = Field(default="Unknown URL")
    timestamp: datetime = Field(default_factory=datetime.now)

# --- APP INITIALIZATION ---
app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_backup()
    SQLModel.metadata.create_all(engine)

# --- SECURITY CONFIG (KEEPING YOUR LOGIC) ---
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_keep_it_safe")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SERVER_SESSION_ID = str(uuid.uuid4())
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- AUTH LOGIC (KEEPING YOUR LOGIC) ---
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("sid") != SERVER_SESSION_ID:
            raise HTTPException(status_code=401, detail="Session expired")
        return payload.get("sub")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != "admin" or form_data.password != "12345":
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return {
        "access_token": jwt.encode({"sub": form_data.username, "sid": SERVER_SESSION_ID}, SECRET_KEY, algorithm=ALGORITHM),
        "token_type": "bearer"
    }

# --- PROTECTED TODO ROUTES ---

@app.get("/todos", response_model=List[TodoRead]) # Use TodoRead here
async def get_todos(user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    statement = select(Todo).options(selectinload(Todo.subTasks))
    results = session.exec(statement).all()
    return results

@app.post("/todos", response_model=TodoRead)
async def add_todo(
        todo_input: TodoCreate, # Changed from Todo to TodoCreate
        user: str = Depends(get_current_user),
        session: Session = Depends(get_session)
):
    # 1. Create the main Todo table object (ignore subtasks for a second)
    db_todo = Todo(
        task=todo_input.task,
        completed=todo_input.completed,
        priority=todo_input.priority,
        dueDate=todo_input.dueDate,
        remindMe=todo_input.remindMe
    )

    session.add(db_todo)
    session.flush() # This generates the Todo ID without closing the transaction

    # 2. Create the SubTask table objects and link them to the Todo ID
    if todo_input.subTasks:
        for st_data in todo_input.subTasks:
            new_sub = SubTask(
                task=st_data.task,
                completed=st_data.completed,
                todo_id=db_todo.id # Link it!
            )
            session.add(new_sub)

    session.commit()
    session.refresh(db_todo)
    return db_todo

@app.put("/todos/{todo_id}", response_model=TodoRead)
async def update_todo(
        todo_id: int,
        updated_data: TodoUpdate, # Changed from Todo to TodoUpdate
        user: str = Depends(get_current_user),
        session: Session = Depends(get_session)
):
    db_todo = session.get(Todo, todo_id)
    if not db_todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # 1. Update basic Todo fields (task, completed, priority, etc.)
    # .dict(exclude_unset=True) ensures we only change what was sent
    update_dict = updated_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        if key != "subTasks":
            setattr(db_todo, key, value)

    # 2. Handle Subtasks (The "Clear and Replace" strategy)
    # We delete existing subtasks first to avoid orphaned rows
    statement = select(SubTask).where(SubTask.todo_id == todo_id)
    existing_subtasks = session.exec(statement).all()
    for sub in existing_subtasks:
        session.delete(sub)

    # 3. Create NEW SubTask table objects from the incoming data
    if updated_data.subTasks:
        for sub_data in updated_data.subTasks:
            # We convert the SubTaskCreate object into a real SubTask table object
            new_sub = SubTask(
                task=sub_data.task,
                completed=sub_data.completed,
                todo_id=todo_id
            )
            session.add(new_sub)

    session.add(db_todo)
    session.commit()
    session.refresh(db_todo)
    return db_todo
@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int, user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    todo = session.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    session.delete(todo)
    session.commit()
    return {"message": "Deleted"}

# --- LOGGING ROUTES ---

@app.get("/logs", response_model=List[LogEntry])
async def get_logs(user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.exec(select(LogEntry)).all()

@app.post("/logs")
async def create_log(data: dict, session: Session = Depends(get_session)):
    try:
        # 1. Manually create the LogEntry object.
        # This ensures 'timestamp' is a real Python datetime object.
        new_log = LogEntry(
            id=data.get("id") or str(uuid.uuid4())[:8],
            message=data.get("message", "No message provided"),
            stack=data.get("stack", "No stack trace"),
            url=data.get("url", "Unknown URL"),
            timestamp=datetime.now() # We use the server's current time
        )

        session.add(new_log)
        session.commit()
        return {"status": "success"}
    except Exception as e:
        session.rollback()
        print(f"CRITICAL DATABASE ERROR: {e}")
        # Log the actual error to the console so you can see it
        raise HTTPException(status_code=500, detail=str(e))
