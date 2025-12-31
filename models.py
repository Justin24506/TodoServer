from datetime import datetime
from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON

class SubTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
task: str
completed: bool = False
todo_id: Optional[int] = Field(default=None, foreign_key="todo.id")
todo: Optional["Todo"] = Relationship(back_populates="subTasks")

class Todo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
task: str
completed: bool = False
priority: str = "Medium"
dueDate: Optional[str] = None
startDate: Optional[str] = None
reminderDate: Optional[str] = None
remindMe: bool = False
# Store Notes as a JSON list in a single column for simplicity
notes: List[str] = Field(default=[], sa_type=JSON)

subTasks: List[SubTask] = Relationship(back_populates="todo", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class ErrorLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
message: str
stack: str
url: str
timestamp: datetime = Field(default_factory=datetime.utcnow)