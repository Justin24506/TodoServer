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

# 1. Define Priority Enum to match 'High' | 'Medium' | 'Low' | null
class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class SubTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task: str
    completed: bool = False

    # Link to Todo
    todo_id: Optional[int] = Field(default=None, foreign_key="todo.id")
    todo: Optional["Todo"] = Relationship(back_populates="subTasks")

class Todo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task: str
    completed: bool = False

    # Matching TypeScript: priority?: Priority
    priority: Optional[Priority] = Field(default=None)

    # Matching TypeScript: dueDate?: string | null
    dueDate: Optional[str] = None

    # Matching TypeScript: startDate?: Date | string | null
    startDate: Optional[str] = None

    # Matching TypeScript: Notes?: string[] (Note the Capital 'N')
    Notes: List[str] = Field(default=[], sa_column=Column(JSON))

    # Matching TypeScript: remindMe?: boolean | null
    remindMe: Optional[bool] = False

    # Matching TypeScript: reminderDate?: Date | string | null
    reminderDate: Optional[str] = None

    # Relationship name must match 'subTasks' in your Interface
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