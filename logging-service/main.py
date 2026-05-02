from contextlib import asynccontextmanager
import os, socket, httpx, hazelcast, base64
from fastapi import FastAPI
from pydantic import BaseModel

CONSUL_URL = f"http://{os.getenv('CONSUL_HOST', 'consul')}:{os.getenv('CONSUL_PORT', '8500')}"
MY_HOSTNAME = os.getenv("MY_HOST", socket.gethostname())
SERVICE_NAME = "logging-service"
SERVICE_ID = f"{SERVICE_NAME}-{MY_HOSTNAME}"

async def fetch_kv(client: httpx.AsyncClient, key: str):
    try:
        resp = await client.get(f"{CONSUL_URL}/v1/kv/{key}")
        resp.raise_for_status()
        encoded = resp.json()[0]['Value']
        return base64.b64decode(encoded).decode('utf-8')
    except Exception as e:
        print(f"LOG: Failed to fetch {key} from Consul: {e}")
        return None

@asynccontextmanager
async def lifespan(app_: FastAPI):
    async with httpx.AsyncClient() as http_client:
        # Fetch configurations from Consul KV
        hz_servers_str = await fetch_kv(http_client, "config/hazelcast/servers")
        hz_servers = hz_servers_str.split(",") if hz_servers_str else ["hz-node-1:5701"]
        hz_cluster_name = await fetch_kv(http_client, "config/hazelcast/cluster_name") or "log"

        # Register Service
        registration_payload = {
            "ID": SERVICE_ID,
            "Name": SERVICE_NAME,
            "Address": MY_HOSTNAME,
            "Port": 8000,
            "Check": {
                "HTTP": f"http://{MY_HOSTNAME}:8000/health",
                "Interval": "10s",
                "Timeout": "5s"
            }
        }
        await http_client.put(f"{CONSUL_URL}/v1/agent/service/register", json=registration_payload)
        print(f"LOG: Registered {SERVICE_ID} with Consul")

    # Connect to Hazelcast
    hz_client = hazelcast.HazelcastClient(cluster_members=hz_servers, cluster_name=hz_cluster_name)
    app_.state.hz_map = hz_client.get_map("logmap").blocking()
    app_.state.hz_client = hz_client

    yield

    # Cleanup
    async with httpx.AsyncClient() as http_client:
        await http_client.put(f"{CONSUL_URL}/v1/agent/service/deregister/{SERVICE_ID}")
    app_.state.hz_client.shutdown()

app = FastAPI(lifespan=lifespan)

class LogTransactionRequest(BaseModel):
    transaction_id: str
    user_id: str
    amount: float

@app.get("/health")
def health():
    return {"status": "UP"}

@app.post("/log")
def log_transaction(data: LogTransactionRequest):
    transaction_data = {"user_id": data.user_id, "amount": data.amount}
    app.state.hz_map.put(data.transaction_id, transaction_data)
    return {"status": "logged"}

@app.get("/logs/{user_id}")
def get_user_logs(user_id: str):
    user_transactions = []
    for tr_id, t in app.state.hz_map.entry_set():
        if t.get("user_id") == user_id:
            user_transactions.append({"transaction_id": tr_id, **t})
    return user_transactions

@app.post("/reset")
def reset_logs():
    app.state.hz_map.clear()
    return {"status": "logs cleared"}
