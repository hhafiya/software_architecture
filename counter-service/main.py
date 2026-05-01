import os
import time
import threading
from contextlib import asynccontextmanager
import socket
import httpx
import psycopg2
import hazelcast
from fastapi import FastAPI

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/balances")
HZ_SERVERS = os.getenv("HZ_SERVERS", "hz-node-1:5701,hz-node-2:5701,hz-node-3:5701").split(",")

def init_db():
    for i in range(5):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    user_id TEXT PRIMARY KEY,
                    balance NUMERIC DEFAULT 0
                )
            ''')
            conn.commit()
            cur.close()
            conn.close()
            print("DATABASE: Table verified")
            return
        except psycopg2.OperationalError:
            print(f"DATABASE: Retry {i+1}/5...")
            time.sleep(2)

def start_queue_worker():
    print("WORKER: Connecting to Hazelcast...")
    hz_client = hazelcast.HazelcastClient(cluster_members=HZ_SERVERS, cluster_name="log")
    queue = hz_client.get_queue("counter-queue").blocking()

    print("WORKER: Ready and listening to 'counter-queue'...")
    db_conn = psycopg2.connect(DATABASE_URL)

    while True:
        try:
            data = queue.take() 
            print(f"WORKER: Processing transaction for {data['user_id']}")

            cur = db_conn.cursor()
            cur.execute('''
                INSERT INTO accounts (user_id, balance) 
                VALUES (%s, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET balance = accounts.balance + EXCLUDED.balance
            ''', (data['user_id'], data['amount']))
            db_conn.commit()
            cur.close()
        except (psycopg2.Error, KeyError, TypeError, ValueError) as e:
            print(f"WORKER ERROR: {e}")
            time.sleep(1)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    worker_thread = threading.Thread(target=start_queue_worker, daemon=True)
    worker_thread.start()

    yield
    print("COUNTER: Shutting down")

app = FastAPI(lifespan=lifespan)

@app.get("/balance/{user_id}")
def get_balance(user_id: str):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('SELECT balance FROM accounts WHERE user_id = %s', (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {"user_id": user_id, "balance": row[0] if row else 0}

@app.get("/balances")
def get_all_balances():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('SELECT user_id, balance FROM accounts')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row[0]: row[1] for row in rows}

@app.post("/reset")
def reset():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('DELETE FROM accounts')
    conn.commit()
    cur.close()
    conn.close()
    return {"status": "reset"}
