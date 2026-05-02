import os, time, threading, socket, httpx, base64
import psycopg2, hazelcast
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

CONSUL_URL = f"http://{os.getenv('CONSUL_HOST', 'consul')}:{os.getenv('CONSUL_PORT', '8500')}"
MY_HOSTNAME = os.getenv("MY_HOST", socket.gethostname())
SERVICE_NAME = "counter-service"
SERVICE_ID = f"{SERVICE_NAME}-{MY_HOSTNAME}"

def init_db(db_url):
    for _ in range(5):
        try:
            with psycopg2.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute('''
                        CREATE TABLE IF NOT EXISTS accounts (
                            user_id TEXT PRIMARY KEY,
                            balance NUMERIC DEFAULT 0
                        )
                    ''')
            print("DATABASE: Table verified")
            return
        except psycopg2.OperationalError:
            time.sleep(2)

def start_queue_worker(hz_servers, queue_name, hz_cluster_name, db_url):
    hz_client = hazelcast.HazelcastClient(cluster_members=hz_servers, cluster_name=hz_cluster_name)
    queue = hz_client.get_queue(queue_name).blocking()
    db_conn = psycopg2.connect(db_url)

    print(f"WORKER: Ready and listening to {queue_name}")
    while True:
        try:
            data = queue.take() 
            cur = db_conn.cursor()
            cur.execute('''
                INSERT INTO accounts (user_id, balance) 
                VALUES (%s, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET balance = accounts.balance + EXCLUDED.balance
            ''', (data['user_id'], data['amount']))
            db_conn.commit()
            cur.close()
        except Exception as e:
            print(f"WORKER ERROR: {e}")
            time.sleep(1)

async def fetch_kv(client: httpx.AsyncClient, key: str):
    try:
        resp = await client.get(f"{CONSUL_URL}/v1/kv/{key}")
        resp.raise_for_status()
        return base64.b64decode(resp.json()[0]['Value']).decode('utf-8')
    except Exception as e:
        print(f"LOG: Failed to fetch {key} from Consul: {e}")
        return None

@asynccontextmanager
async def lifespan(app_: FastAPI):
    async with httpx.AsyncClient() as http_client:
        hz_servers_str = await fetch_kv(http_client, "config/hazelcast/servers")
        hz_servers = hz_servers_str.split(",") if hz_servers_str else ["hz-node-1:5701"]
        hz_cluster_name = await fetch_kv(http_client, "config/hazelcast/cluster_name") or "log"
        queue_name = await fetch_kv(http_client, "config/mq/queue_name") or "counter-queue"

        db_url = await fetch_kv(http_client, "config/db/url")
        app_.state.db_url = db_url or "postgresql://user:password@db:5432/balances"

        registration_payload = {
            "ID": SERVICE_ID, "Name": SERVICE_NAME, "Address": MY_HOSTNAME, "Port": 8000,
            "Check": {"HTTP": f"http://{MY_HOSTNAME}:8000/health", "Interval": "10s"}
        }
        await http_client.put(f"{CONSUL_URL}/v1/agent/service/register", json=registration_payload)

    init_db(app_.state.db_url)

    worker_thread = threading.Thread(target=start_queue_worker,
                                     args=(hz_servers, queue_name, hz_cluster_name, app_.state.db_url), daemon=True)
    worker_thread.start()

    yield

    async with httpx.AsyncClient() as http_client:
        await http_client.put(f"{CONSUL_URL}/v1/agent/service/deregister/{SERVICE_ID}")

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "UP"}

@app.get("/balance/{user_id}")
def get_balance(user_id: str, request: Request):
    db_url = request.app.state.db_url
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT balance FROM accounts WHERE user_id = %s', (user_id,))
            row = cur.fetchone()
    return {"user_id": user_id, "balance": row[0] if row else 0}

@app.get("/balances")
def get_all_balances(request: Request):
    db_url = request.app.state.db_url
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT user_id, balance FROM accounts')
            rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}

@app.post("/reset")
def reset(request: Request):
    db_url = request.app.state.db_url
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM accounts')
    return {"status": "reset"}
