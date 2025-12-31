import os
from datetime import datetime, timedelta
from typing import List, Optional
import jwt # Using PyJWT as discussed
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, create_engine, select
from models import Todo, SubTask, TodoCreate, ErrorLog, SQLModel
from sqlalchemy.orm import selectinload

# --- 1. Database & Security Config ---
DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql://user:pass@localhost/dbname").replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL)

SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# --- 2. Helpers ---
def get_session():
    with Session(engine) as session:
        yield session

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --- 3. Auth Routes ---
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != "admin" or form_data.password != "12345":
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/todos", response_model=List[Todo])
async def get_todos(session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    # .options(selectinload(Todo.subTasks)) tells SQLModel to grab the children immediately
    statement = select(Todo).options(selectinload(Todo.subTasks))
    return session.exec(statement).all()

@app.get("/todos/{todo_id}", response_model=Todo)
async def get_todo(todo_id: int, session: Session = Depends(get_session)):
    # For a single item, we use the same loading strategy
    statement = select(Todo).where(Todo.id == todo_id).options(selectinload(Todo.subTasks))
    todo = session.exec(statement).first()

    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo

@app.post("/todos")
async def add_todo(todo_input: TodoCreate, session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    try:
        # 1. Create the DB version of the Todo
        db_todo = Todo(
            task=todo_input.task,
            completed=todo_input.completed,
            priority=todo_input.priority,
            dueDate=todo_input.dueDate,
            startDate=todo_input.startDate,
            Notes=todo_input.Notes,
            remindMe=todo_input.remindMe,
            reminderDate=todo_input.reminderDate
        )

        session.add(db_todo)
        session.commit()
        session.refresh(db_todo)

        # 2. Handle subtasks separately
        if todo_input.subTasks:
            for st in todo_input.subTasks:
                new_subtask = SubTask(
                    task=st.task,
                    completed=st.completed,
                    todo_id=db_todo.id
                )
                session.add(new_subtask)
            session.commit()
            session.refresh(db_todo)

        return db_todo
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/todos/{todo_id}")
async def update_todo(todo_id: int, updated_todo: TodoCreate, session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    db_todo = session.get(Todo, todo_id)
    if not db_todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    try:
        # Update fields
        for key, value in updated_todo.model_dump(exclude={"subTasks"}).items():
            setattr(db_todo, key, value)

        # Sync Subtasks
        if updated_todo.subTasks is not None:
            # Delete old
            for old_st in db_todo.subTasks:
                session.delete(old_st)

            # Add new
            for st in updated_todo.subTasks:
                session.add(SubTask(task=st.task, completed=st.completed, todo_id=db_todo.id))

        session.add(db_todo)
        session.commit()
        session.refresh(db_todo)
        return db_todo
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# @app.post("/todos")
# async def add_todo(todo_input: Todo, session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
#     try:
#         # 1. Take the subtasks out of the incoming data
#         # We use .dict() or .model_dump() to get the raw data
#         incoming_data = todo_input.model_dump()
#         raw_subtasks = incoming_data.pop("subTasks", [])
#
#         # 2. Create Todo without the subtasks list and without the ID
#         if "id" in incoming_data: del incoming_data["id"]
#
#         db_todo = Todo(**incoming_data)
#         session.add(db_todo)
#         session.commit() # Save parent to generate db_todo.id
#         session.refresh(db_todo)
#
#         # 3. If there are subtasks, create them manually
#         if raw_subtasks:
#             for st_data in raw_subtasks:
#                 # Remove the ID from subtask if Angular sent one (like 0 or null)
#                 if "id" in st_data: del st_data["id"]
#
#                 new_st = SubTask(
#                     task=st_data["task"],
#                     completed=st_data["completed"],
#                     todo_id=db_todo.id # Explicitly link to parent
#                 )
#                 session.add(new_st)
#
#             session.commit()
#             session.refresh(db_todo)
#
#         return db_todo
#     except Exception as e:
#         session.rollback()
#         print(f"CRITICAL ERROR: {str(e)}") # Check Vercel Logs!
#         raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")


@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int, session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    todo = session.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    session.delete(todo)
    session.commit()
    return {"message": "Deleted successfully"}

# --- Bulk Actions (For your Floating Toolbar) ---

@app.post("/todos/bulk-delete")
async def bulk_delete(ids: List[int], session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    statement = select(Todo).where(Todo.id.in_(ids)).options(selectinload(Todo.subTasks))
    results = session.exec(statement).all()

    if not results:
        return {"message": "No tasks found to delete"}

    for todo in results:
        # The database relationship usually handles subtask deletion,
        # but we delete the parent here explicitly.
        session.delete(todo)

    session.commit()
    return {"message": f"Deleted {len(results)} tasks and associated subtasks"}

@app.post("/todos/bulk-status")
async def bulk_status(payload: dict, session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    ids = payload.get("ids", [])
    completed_val = payload.get("completed", False)

    # Fetch todos with their subtasks
    statement = select(Todo).where(Todo.id.in_(ids)).options(selectinload(Todo.subTasks))
    results = session.exec(statement).all()

    for todo in results:
        todo.completed = completed_val
        # Also update all associated subtasks to match
        for sub in todo.subTasks:
            sub.completed = completed_val
        session.add(todo)

    session.commit()
    return {"message": f"Updated {len(results)} tasks and their subtasks"}

# --- 5. Logs Route ---
@app.post("/logs")
async def save_log(log: ErrorLog, session: Session = Depends(get_session)):
    session.add(log)
    session.commit()
    return {"status": "success"}

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)