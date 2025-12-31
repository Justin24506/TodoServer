# models.py
# from datetime import datetime
# from typing import List, Optional
# from sqlmodel import SQLModel, Field, Relationship
# from sqlalchemy import JSON, Column

from datetime import datetime
from typing import List, Optional
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON

class SubTaskBase(SQLModel):
    task: str
    completed: bool = False

class SubTask(SubTaskBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    todo_id: Optional[int] = Field(default=None, foreign_key="todo.id")
    todo: Optional["Todo"] = Relationship(back_populates="subTasks")

class TodoBase(SQLModel):
    task: str
    completed: bool = False
    priority: Optional[str] = "Medium"
    dueDate: Optional[str] = None
    startDate: Optional[str] = None
    Notes: List[str] = Field(default=[]) # No sa_column here
    remindMe: bool = False
    reminderDate: Optional[str] = None

class Todo(TodoBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # We add the DB-specific field here
    Notes: List[str] = Field(default=[], sa_column=Column(JSON))

    subTasks: List[SubTask] = Relationship(
        back_populates="todo",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

# THIS IS THE KEY: A separate class for incoming data
class TodoCreate(TodoBase):
    subTasks: Optional[List[SubTaskBase]] = None

class ErrorLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    message: str
    stack: Optional[str] = None
    url: str
    level: str = "Error"  # Default to Error
    timestamp: datetime = Field(default_factory=datetime.utcnow)