# models.py
from datetime import datetime
from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import JSON, Column

class SubTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task: str  # <--- INDENTED
    completed: bool = False
    todo_id: Optional[int] = Field(default=None, foreign_key="todo.id")

    todo: Optional["Todo"] = Relationship(back_populates="subTasks")

class Todo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task: str  # <--- INDENTED
    completed: bool = False
    priority: str = "Medium"
    dueDate: Optional[str] = None
    startDate: Optional[str] = None
    reminderDate: Optional[str] = None
    remindMe: bool = False
    # Use sa_column for complex types like JSON in SQLModel
    notes: List[str] = Field(default=[], sa_column=Column(JSON))

    subTasks: List[SubTask] = Relationship(
        back_populates="todo",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class ErrorLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    message: str
    stack: Optional[str] = None
    url: str
    level: str = "Error"  # Default to Error
    timestamp: datetime = Field(default_factory=datetime.utcnow)