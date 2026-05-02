from contextlib import asynccontextmanager
import os, time, random, socket, httpx, hazelcast, base64, asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

CONSUL_URL = f"http://{os.getenv('CONSUL_HOST', 'consul')}:{os.getenv('CONSUL_PORT', '8500')}"
MY_HOSTNAME = os.getenv("MY_HOST", socket.gethostname())
SERVICE_NAME = "facade-service"
SERVICE_ID = f"{SERVICE_NAME}-{MY_HOSTNAME}"

service_cache = {}
CACHE_TTL = 5.0  # Cache IPs for 5 seconds

async def fetch_kv(client: httpx.AsyncClient, key: str):
    try:
        resp = await client.get(f"{CONSUL_URL}/v1/kv/{key}")
        resp.raise_for_status()
        return base64.b64decode(resp.json()[0]['Value']).decode('utf-8')
    except Exception:
        return None

@asynccontextmanager
async def lifespan(app_: FastAPI):
    app_.state.http_client = httpx.AsyncClient()

    # Read settings from Config Server (Consul KV)
    hz_servers_str = await fetch_kv(app_.state.http_client, "config/hazelcast/servers")
    hz_servers = hz_servers_str.split(",") if hz_servers_str else ["hz-node-1:5701"]
    queue_name = await fetch_kv(app_.state.http_client, "config/mq/queue_name") or "counter-queue"

    hz_client = hazelcast.HazelcastClient(cluster_members=hz_servers, cluster_name="log")
    app_.state.queue = hz_client.get_queue(queue_name).blocking()
    app_.state.hz_client = hz_client

    app_.state.stats = {"logging_time_total": 0.0, "counter_time_total": 0.0, "request_count": 0}

    # Self-register
    registration = {
        "ID": SERVICE_ID, "Name": SERVICE_NAME, "Address": MY_HOSTNAME, "Port": 8000,
        "Check": {"HTTP": f"http://{MY_HOSTNAME}:8000/health", "Interval": "10s"}
    }
    await app_.state.http_client.put(f"{CONSUL_URL}/v1/agent/service/register", json=registration)

    yield

    await app_.state.http_client.put(f"{CONSUL_URL}/v1/agent/service/deregister/{SERVICE_ID}")
    hz_client.shutdown()
    await app_.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)

async def get_service_url(target_service: str):
    now = time.time()
    if target_service in service_cache and service_cache[target_service]["expires_at"] > now:
        return random.choice(service_cache[target_service]["urls"])

    try:
        resp = await app.state.http_client.get(
            f"{CONSUL_URL}/v1/health/service/{target_service}?passing=true", timeout=2.0
        )
        services = resp.json()
        if not services:
            raise HTTPException(status_code=503, detail=f"No healthy nodes for {target_service}")

        urls = [f"http://{s['Service']['Address']}:{s['Service']['Port']}" for s in services]
        service_cache[target_service] = {"urls": urls, "expires_at": now + CACHE_TTL}

        return random.choice(urls)
    except httpx.HTTPError as e:
        if target_service in service_cache:
            return random.choice(service_cache[target_service]["urls"])
        raise HTTPException(status_code=503, detail=f"Consul discovery failed: {e}")

class TransactionRequest(BaseModel):
    user_id: str
    amount: float

async def log_task(payload: dict):
    start = time.perf_counter()
    try:
        log_url = await get_service_url("logging-service")
        await app.state.http_client.post(f"{log_url}/log", json=payload, timeout=1.5)
    except (HTTPException, httpx.HTTPError) as e:
        print(f"FACADE: Logging failed: {e}")
    return time.perf_counter() - start

async def counter_task(payload: dict):
    start = time.perf_counter()
    await asyncio.to_thread(app.state.queue.put, payload)
    return time.perf_counter() - start

@app.get("/health")
def health():
    return {"status": "UP"}

@app.post("/transaction")
async def create_transaction(data: TransactionRequest):
    transaction_id = str(int(time.time() * 1000))
    payload = {"transaction_id": transaction_id, "user_id": data.user_id, "amount": data.amount}

    log_dur, counter_dur = await asyncio.gather(
        log_task(payload),
        counter_task(payload)
    )

    app.state.stats["logging_time_total"] += log_dur
    app.state.stats["counter_time_total"] += counter_dur
    app.state.stats["request_count"] += 1

    return {"transaction_id": transaction_id, "status": "accepted"}

@app.get("/user/{user_id}")
async def get_user_info(user_id: str):
    try:
        c_url = await get_service_url("counter-service")
        l_url = await get_service_url("logging-service")

        balance_resp = await app.state.http_client.get(f"{c_url}/balance/{user_id}")
        logs_resp = await app.state.http_client.get(f"{l_url}/logs/{user_id}")

        return {"balance": balance_resp.json().get("balance"), "transactions": logs_resp.json()}
    except (HTTPException, httpx.HTTPError) as e:
        return {"balance": None, "transactions": [], "error": str(e)}

@app.get("/accounts")
async def get_all_accounts():
    try:
        c_url = await get_service_url("counter-service")
        resp = await app.state.http_client.get(f"{c_url}/balances", timeout=2.0)
        return resp.json()
    except (httpx.HTTPError, HTTPException):
        return {"error": "Counter service unavailable", "accounts": []}

@app.get("/stats")
def get_stats():
    return app.state.stats

@app.post("/reset")
async def reset_all_systems():
    app.state.stats.update({"logging_time_total": 0.0,
                            "counter_time_total": 0.0,
                            "request_count": 0})
    try:
        c_url = await get_service_url("counter-service")
        await app.state.http_client.post(f"{c_url}/reset")
        l_url = await get_service_url("logging-service")
        await app.state.http_client.post(f"{l_url}/reset")
    except (HTTPException, httpx.HTTPError):
        pass
    return {"status": "reset request sent"}
