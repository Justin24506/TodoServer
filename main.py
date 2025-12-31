import os
from datetime import datetime, timedelta
from typing import List, Optional
import jwt # Using PyJWT as discussed
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, create_engine, select
from models import Todo, SubTask, ErrorLog, SQLModel # Assumes models.py exists

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

# --- 4. Todo Routes (Migration of your JSON logic) ---

@app.get("/todos", response_model=List[Todo])
async def get_todos(session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    # SQLModel relationship handles subTasks automatically
    return session.exec(select(Todo)).all()

@app.get("/todos/{todo_id}", response_model=Todo)
async def get_todo(todo_id: int, session: Session = Depends(get_session)):
    todo = session.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todo

@app.post("/todos")
async def add_todo(todo_input: Todo, session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    # 1. Extract subtasks from the incoming data
    subtask_data = todo_input.subTasks

    # 2. Create the Todo object WITHOUT subtasks first
    # We exclude 'subTasks' and 'id' to create a clean parent record
    todo_dict = todo_input.model_dump(exclude={"subTasks", "id"})
    db_todo = Todo(**todo_dict)

    session.add(db_todo)
    session.commit() # This saves the Todo and generates the ID
    session.refresh(db_todo) # Now db_todo.id exists!

    # 3. Create and link SubTasks if they exist
    if subtask_data:
        for st in subtask_data:
            # Create a real SubTask object and link it to the new Todo ID
            new_subtask = SubTask(
                task=st.task,
                completed=st.completed,
                todo_id=db_todo.id
            )
            session.add(new_subtask)

        session.commit()
        session.refresh(db_todo) # Refresh again to include the subtasks in the response

    return db_todo

@app.put("/todos/{todo_id}")
async def update_todo(todo_id: int, updated_todo: Todo, session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    db_todo = session.get(Todo, todo_id)
    if not db_todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # Update main Todo fields
    todo_data = updated_todo.model_dump(exclude={"subTasks", "id"}, exclude_unset=True)
    for key, value in todo_data.items():
        setattr(db_todo, key, value)

    # Simple SubTask sync: Delete old ones and add new ones
    # (This is the fastest way to handle updates for a simple app)
    if updated_todo.subTasks is not None:
        # Delete existing subtasks
        for existing_st in db_todo.subTasks:
            session.delete(existing_st)

        # Add new ones
        for st in updated_todo.subTasks:
            new_st = SubTask(task=st.task, completed=st.completed, todo_id=db_todo.id)
            session.add(new_st)

    session.add(db_todo)
    session.commit()
    session.refresh(db_todo)
    return db_todo

@app.delete("/todos/{todo_id}")
async def delete_todo(todo_id: int, session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    todo = session.get(Todo, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    session.delete(todo)
    session.commit()
    return {"message": "Deleted"}

# --- 5. Logs Route ---
@app.post("/logs")
async def save_log(log: ErrorLog, session: Session = Depends(get_session)):
    session.add(log)
    session.commit()
    return {"status": "success"}

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)