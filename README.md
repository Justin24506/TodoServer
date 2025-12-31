# Todo Server API

A technical backend implementation using FastAPI and SQLModel. This service manages a relational Todo database with subtask support, JWT authentication, and automated error logging.

## 🛠 Tech Stack

* **Runtime:** Python 3.11+
* **Framework:** [FastAPI](https://fastapi.tiangolo.com/)
* **ORM:** [SQLModel](https://sqlmodel.tiangolo.com/) (SQLAlchemy + Pydantic)
* **Database:** PostgreSQL (via Vercel/Neon)
* **Package Manager:** [uv](https://github.com/astral-sh/uv)
* **Security:** JWT (PyJWT) & Bcrypt (Passlib)

---

## ⚙️ Local Setup

1.  **Install dependencies:**
    ```bash
    uv sync
    ```

2.  **Configure environment:**
    Create a `.env` file in the root directory:
    ```text
    POSTGRES_URL=postgresql://user:password@localhost:5432/dbname
    SECRET_KEY=your_generated_hex_key
    ALGORITHM=HS256
    ```

3.  **Run the application:**
    ```bash
    uv run uvicorn main:app --reload
    ```

---

## 🔄 Data Migration

To migrate existing `db.json` data to the Postgres instance:

```bash
uv run migrate.py
