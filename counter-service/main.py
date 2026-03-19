import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/balances")

def init_db():
    for i in range(5):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    user_id TEXT PRIMARY KEY,
                    balance INTEGER DEFAULT 0
                )
            ''')
            conn.commit()
            cur.close()
            conn.close()
            print("DATABASE: Table created/verified successfully")
            return
        except psycopg2.OperationalError:
            print(f"DATABASE: Not ready, retrying in 2s... ({i+1}/5)")
            time.sleep(2)
    raise RuntimeError("Could not connect to the database")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    print("DATABASE: Shutting down counter-service")

app = FastAPI(lifespan=lifespan)

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

class UpdateRequest(BaseModel):
    user_id: str
    amount: int

@app.post("/update")
def update_balance(data: UpdateRequest):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO accounts (user_id, balance) 
            VALUES (%s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET balance = accounts.balance + EXCLUDED.balance
            RETURNING balance
        ''', (data.user_id, data.amount))

        new_balance = cur.fetchone()[0]
        conn.commit()
        return {"user_id": data.user_id, "balance": new_balance}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        cur.close()
        conn.close()

@app.get("/balance/{user_id}")
def get_balance(user_id: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT balance FROM accounts WHERE user_id = %s', (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    return {"user_id": user_id, "balance": row[0] if row else 0}

@app.get("/balances")
def get_all_balances():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT user_id, balance FROM accounts')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row[0]: row[1] for row in rows}

@app.post("/reset")
def reset():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM accounts')
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "reset"}
