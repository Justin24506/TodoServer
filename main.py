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
    allow_origins=["http://localhost:4200", "*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
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
async def add_todo(todo_data: Todo, session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    # Postgres handles ID incrementing automatically (no need to max(ids) + 1)
    session.add(todo_data)
    session.commit()
    session.refresh(todo_data)
    return todo_data

@app.put("/todos/{todo_id}")
async def update_todo(todo_id: int, updated_todo: Todo, session: Session = Depends(get_session), token: str = Depends(oauth2_scheme)):
    db_todo = session.get(Todo, todo_id)
    if not db_todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    # Update fields from the request
    todo_data = updated_todo.dict(exclude_unset=True)
    for key, value in todo_data.items():
        setattr(db_todo, key, value)

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